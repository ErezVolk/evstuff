#!/usr/bin/env python3
"""Italicize math"""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile

from typing import Iterator

from lxml import etree


class Mathicizer:
    """Italicize match in .docx"""

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--input", type=Path)
        parser.add_argument("-o", "--output", type=Path)
        parser.add_argument("-x", "--extract", action="store_true")
        parser.add_argument("-y", "--no-postract", action="store_true")
        parser.add_argument("-s", "--style", default="נוסחה")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--open", action="store_true")
        parser.add_argument("--extract-to", type=Path, default="play")
        self.args = parser.parse_args()
        self.figure_out_paths(parser)

    DOC_IN_ZIP = "word/document.xml"
    STYLES_IN_ZIP = "word/styles.xml"
    _FORMULA_XPATH_FORMAT = (
        "//w:r[w:rPr[w:rStyle[@w:val='{style_id}'] and not(w:i)] and w:t]"
    )
    _SUSPECT_XPATH_FORMAT = (
        "//w:r[w:rPr[(not(w:rStyle) or w:rStyle[@w:val!='{style_id}']) and not(w:rtl)] and w:t]"
    )
    ISLAND_XPATH = (
        "//w:r[not(w:rPr/w:rtl) and w:t[@xml:space='preserve']]"
    )
    ITALICABLE_RE = r"\b([A-Z]{0,2}[a-z][A-Za-z]*|[A-Z])\b"
    SUSPECT_RE = r"(^\s*[A-Z]\s*$|\bP\()"
    _W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _NS = {"w": _W}
    LOCK_MARK = "~$"

    args: argparse.Namespace
    counts: Counter = Counter()
    doc: etree._ElementTree
    formula_xpath: str
    izip: ZipFile
    root: etree._Entity
    suspect_xpath: str

    def main(self):
        """Italicize math"""
        self.parse_args()

        print(f"Reading {self.args.input}")
        with ZipFile(self.args.input) as self.izip:
            self._work()

    def figure_out_paths(self, parser: argparse.ArgumentParser):
        """Find input and output, if not given"""
        if self.args.output and not self.args.input:
            parser.error("You cannot specify --output without --input")

        if self.args.input and self.args.output:
            return

        if self.args.input and not self.args.output:
            self._set_output_from_input()
            return

        docxs = [
            path
            for path in Path.cwd().glob("*.docx")
            if not path.stem.startswith(self.LOCK_MARK)
        ]

        if len(docxs) == 0:
            parser.error("No .docx files, please specify --input")

        if len(docxs) == 1:
            self.args.input = docxs[0]
            self._set_output_from_input()
            return

        if len(docxs) == 2:
            (fna, fnb) = docxs
            if fnb.stem == fna.stem + "-math":
                (self.args.input, self.args.output) = (fna, fnb)
                return
            if fna.stem == fnb.stem + "-math":
                (self.args.input, self.args.output) = (fnb, fna)
                return

        parser.error("Cannot guess file names, please specify --input")

    def _set_output_from_input(self):
        """Helper"""
        self.args.output = self.args.input.with_stem(f"{self.args.input.stem}-math")

    def _work(self):
        """Work with the open input zip file"""
        with self.izip.open(self.DOC_IN_ZIP) as ifo:
            self.doc = etree.parse(ifo)
            self.root = self.doc.getroot()

        postract = not self.args.no_postract
        if self.args.extract or postract:
            self._save_to("mathicize-input.xml")
            if self.args.extract:
                return

        if not self._may_work():
            print("Cowardly refusing to overwrite open .docx file")
            return

        if not self._mathicize():
            print("Nothing changed.")
            return

        if postract:
            self._save_to("mathicize-output.xml")
        self._write()
        if self.args.open:
            subprocess.run(["open", str(self.args.output)], check=False)

    def _save_to(self, name: str):
        """Save the XML in a nice format"""
        output = self.args.extract_to / name

        print(f"Saving XML to {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        self.doc.write(output, encoding="utf-8", pretty_print=True)

    def _xpath(self, node: etree._Entity, expr: str) -> Iterator[etree._Entity]:
        """Wrapper for etree.xpath, with namespaces"""
        yield from node.xpath(expr, namespaces=self._NS)

    def _first(self, node: etree._Entity, expr: str) -> etree._Entity | None:
        """First entity matching xpath"""
        for entity in self._xpath(node, expr):
            return entity
        return None

    @classmethod
    def _find(cls, node: etree._Entity, expr: str) -> etree._Entity:
        """Wrapper for etree.find, with namespaces"""
        return node.find(expr, namespaces=cls._NS)

    def _may_work(self) -> bool:
        """Check (unless --force) whether the output file is open"""
        lock = self.args.output.with_stem(
            self.LOCK_MARK + self.args.output.stem[len(self.LOCK_MARK):]
        )
        locked = lock.is_file()
        if not locked:
            return True

        print(f"{self.args.output} seems to be open ({lock.name} exists)")
        return self.args.force

    def _mathicize(self) -> bool:
        """Does the heavly lifting on self.doc"""
        self._find_style()
        worked = self._italicize_math()
        worked = self._fix_islands() or worked
        self._note_suspects()
        if worked:
            print("Change counts:")
            mkw = max(len(key) for key in self.counts)
            for key, val in sorted(self.counts.items(), key=lambda kv: kv[1], reverse=True):
                print(f" {key.ljust(mkw)}  {val}")
        return worked

    def _italicize_math(self) -> bool:
        """Convert text in formulas to italics"""
        for rnode in self._xpath(self.root, self.formula_xpath):
            self.counts["considered_for_italics"] += 1
            text = self._rnode_text(rnode)
            relevant = re.search(self.ITALICABLE_RE, text)
            if relevant is None:
                # A dud
                continue

            self.counts["range"] += 1
            if relevant.start() == 0 and relevant.end() == len(text):
                # The simple case: range == italic
                self.counts["full"] += 1
                self.counts["italicized"] += 1
                self._make_italic(rnode)
                continue

            # This is the difficult case: Need to create duplicates
            idx_prev = 0
            for match in re.finditer(self.ITALICABLE_RE, text):
                (idx_from, idx_to) = match.span()
                if idx_prev < idx_from:
                    rnode.addprevious(self._mknode(rnode, text[idx_prev:idx_from], False))
                    self.counts["chunks"] += 1
                if idx_from < idx_to:
                    rnode.addprevious(self._mknode(rnode, text[idx_from:idx_to], True))
                    self.counts["chunks"] += 1
                    self.counts["italicized"] += 1
                idx_prev = idx_to
            if idx_prev < len(text):
                rnode.addprevious(self._mknode(rnode, text[idx_prev:], False))
                self.counts["chunks"] += 1
            rnode.getparent().remove(rnode)

        return self.counts["italicized"] > 0

    def _fix_islands(self) -> bool:
        """Find islands of LTR whitespace in RTL"""
        for rnode in self._xpath(self.root, self.ISLAND_XPATH):
            self.counts["considered_for_island"] += 1
            text = self._rnode_text(rnode)
            if not text.isspace():
                continue

            rprev = rnode.getprevious()
            if not self._is_rtl(rprev):
                continue

            if not self._is_rtl(rnode.getnext()):
                continue

            self._set_rnode_text(rprev, self._rnode_text(rprev) + text)
            rnode.getparent().remove(rnode)

            self.counts["rtlized"] += 1
        return self.counts["rtlized"] > 0

    def _note_suspects(self):
        """Look for text that may be an unmarked formula"""
        for rnode in self._xpath(self.root, self.suspect_xpath):
            self.counts["considered_for_suspect"] += 1
            text = self._rnode_text(rnode)
            if not re.search(self.SUSPECT_RE, text):
                continue
            self.counts["suspect"] += 1
            context = "".join([
                self._rnode_text(rnode.getprevious()),
                text,
                self._rnode_text(rnode.getnext()),
            ])
            print(f"You may want to look at '... {context} ...'")

    def _is_rtl(self, rnode) -> bool:
        """Checks whether a <w:r> node is RTL"""
        return self._first(rnode, "./w:rPr/w:rtl") is not None

    def _find_style(self):
        """Find the right style, set `self.formula_xpath`"""
        with self.izip.open(self.STYLES_IN_ZIP) as ifo:
            styles = etree.parse(ifo).getroot()
        xpath = f"//w:style[w:name[@w:val='{self.args.style}']]"
        node = self._first(styles, xpath)
        if node is None:
            raise ValueError(f'No style named "{self.args.style}" in {self.args.input}')
        style_id = node.get(self._wtag("styleId"))
        self.formula_xpath = self._FORMULA_XPATH_FORMAT.format(style_id=style_id)
        self.suspect_xpath = self._SUSPECT_XPATH_FORMAT.format(style_id=style_id)

    def _mknode(self, model: etree._Entity, text: str, italic: bool) -> etree._Entity:
        """Create a duplicate of `model` with different text, and possibly italics."""
        rnode = deepcopy(model)
        self._set_rnode_text(rnode, text)
        if italic:
            self._make_italic(rnode)
        return rnode

    def _set_rnode_text(self, rnode: etree._Entity, text: str):
        """Helper to replace <w:t> inside <w:r>"""
        tnode = self._find(rnode, "w:t")
        tnode.text = text
        if text[0].isspace() or text[-1].isspace():
            tnode.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    def _make_italic(self, node: etree._Element):
        """Add the italic tag"""
        self._find(node, "w:rPr").append(self._w_i())

    def _write(self):
        """Create the output .docx"""
        print(f"Writing {self.args.output}")
        with ZipFile(self.args.input) as izip, ZipFile(self.args.output, "w") as ozip:
            for info in izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    if info.filename == self.DOC_IN_ZIP:
                        ofo.write(etree.tostring(self.doc))
                    else:
                        with izip.open(info, "r") as ifo:
                            ofo.write(ifo.read())

    @classmethod
    def _wtag(cls, tag: str) -> str:
        return f"{{{cls._W}}}{tag}"

    def _w_i(self) -> etree._Entity:
        """Create <w:i> node"""
        return self.root.makeelement(self._wtag("i"))

    def _w_rtl(self) -> etree._Entity:
        """Create <w:rtl> node"""
        return self.root.makeelement(self._wtag("rtl"))

    @classmethod
    def _rnode_text(cls, rnode: etree._Entity) -> str:
        """Return <w:t> node of a <w:r> node"""
        tnode = cls._find(rnode, "w:t")
        if tnode is None:
            return ""
        return tnode.text

    # MAYB: overwrite original doc, backup somewhere


if __name__ == "__main__":
    Mathicizer().main()

#!/usr/bin/env python3
"""Italicize math"""
import argparse
from collections import Counter
from collections import defaultdict
from copy import deepcopy
import datetime
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile

from typing import Iterator

from bidi.algorithm import get_display
from lxml import etree


class Mathicizer:
    """Italicize math in .docx files."""

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser(description=self.__class__.__doc__)
        parser.add_argument("-i", "--input", type=Path, help="Input .docx file")
        parser.add_argument("-o", "--outdir", type=Path, help="Output directory")
        parser.add_argument(
            "-d",
            "--antidict",
            type=Path,
            default="antidict.txt",
            help="File with one regex per line which should NOT be in the text",
        )
        parser.add_argument(
            "-x",
            "--extract",
            action="store_true",
            help="Only save copy of XML document before processing",
        )
        parser.add_argument(
            "-y",
            "--no-postract",
            action="store_true",
            help="Do NOT save copy of XML after processing",
        )
        parser.add_argument(
            "-s", "--style", default="נוסחה", help="Style name for formulas"
        )
        parser.add_argument(
            "-S", "--anti-style", default="לא נוסחה", help="Style name for non-formulas"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Work even if output file is currently open",
        )
        parser.add_argument(
            "--open", action="store_true", help="Open output file after processing"
        )
        parser.add_argument(
            "--extract-to",
            type=Path,
            default="play",
            help="Folder in which to extract XML files",
        )
        parser.add_argument(
            "--no-overwrite",
            action="store_true",
            help="Do not overwrite input file, even if closed",
        )
        self.args = parser.parse_args()
        self.figure_out_paths(parser)
        self._load_antidict()

    DOC_IN_ZIP = "word/document.xml"
    STYLES_IN_ZIP = "word/styles.xml"
    _FORMULA_XPATH_FORMAT = (
        "//w:r["
        " w:rPr["
        "  w:rStyle[@w:val='{style_id}']"  # Formula style
        "  and"
        "  not(w:i)"  # Not already italicized
        " ]"
        " and"
        " w:t[re:test(., '[a-z]', 'i')]"  # With actual letters
        "]"
    )
    _SUSPECT_XPATH_FORMAT = (
        "//w:r["
        " w:rPr["
        "  (not(w:rStyle) or w:rStyle[@w:val!='{style_id}'])"  # Not formula style
        "  and"
        "  not(w:rtl)"  # But LTR
        " ]"
        " and"
        " w:t[re:test(., '[a-z]', 'i')]"  # With actual letters
        "]"
    )
    _SUSPECT_XPATH_FORMAT_WITH_ANTI_STYLE = (
        "//w:r["
        " w:rPr["
        "  (not(w:rStyle) or w:rStyle[@w:val!='{style_id}' and @w:val!='{anti_style_id}'])"  # Not (anti-)formula style
        "  and"
        "  not(w:rtl)"  # But LTR
        " ]"
        " and"
        " w:t[re:test(., '[a-z]', 'i')]"  # With actual letters
        "]"
    )
    ISLAND_XPATH = (
        "//w:r["
        " not(w:rPr/w:rtl)"  # Is LTR text
        "  and"
        " preceding-sibling::*[1][self::w:r[w:rPr/w:rtl and w:t]]"  # Is after some RTL text
        "  and"
        " following-sibling::*[1][self::w:r[w:rPr/w:rtl and w:t]]"  # Is before some RTL text
        "  and"
        " w:t["
        "  @xml:space='preserve'"  # With whitespace at edge
        "   and"
        "   re:test(., '^ +$')"  # Only whitespace
        " ]"
        "]"
    )
    ITALICABLE_RE = r"\b([A-Z]{0,2}[a-z][A-Za-z]*|[A-Z])\b"
    SUSPECT_RE = r"(^\s*[A-Z]\s*$|\bP\()"
    _W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _NS = {"w": _W, "re": "http://exslt.org/regular-expressions"}
    LOCK_MARK = "~$"

    antidict: re.Pattern | None
    antiwords: Counter = Counter()
    args: argparse.Namespace
    comments: dict = defaultdict(list)
    counts: Counter = Counter()
    doc: etree._ElementTree
    formula_xpath: str
    izip: ZipFile
    opath: Path
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
        if not self.args.input:
            docxs = [
                path
                for path in Path.cwd().glob("*.docx")
                if not path.stem.startswith(self.LOCK_MARK)
            ]

            if len(docxs) != 1:
                parser.error(
                    f"Please specify --input; "
                    f"I can only guess it if there's exactly 1 .docx file "
                    f"(found {len(docxs)})"
                )

            self.args.input = docxs[0]

        if not self.args.outdir:
            now = datetime.datetime.now()
            self.args.outdir = Path("mathicize-out") / now.strftime("%Y%m%d-%H%M")

        self.args.outdir.mkdir(parents=True, exist_ok=True)
        self.opath = self.args.outdir / f"mathicized-{self.args.input.stem}.docx"

    def _work(self):
        """Work with the open input zip file"""
        self._copy(self.args.input, self.args.outdir / "mathicize-input.docx")

        with self.izip.open(self.DOC_IN_ZIP) as ifo:
            self.doc = etree.parse(ifo)
            self.root = self.doc.getroot()

        self._save_to("mathicize-input.xml")

        changed = self._mathicize()
        if changed:
            self._write()
        else:
            print("Nothing changed.")

        self._add_comments()
        self._save_to("mathicize-output.xml")

        if changed:
            self._consider_overwrite()

        if changed and self.args.open:
            subprocess.run(["open", str(self.opath)], check=False)

    def _save_to(self, name: str):
        """Save the XML in a nice format"""
        output = self.args.outdir / name

        print(f"Saving XML to {output}")
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

    def _is_open(self, path: Path) -> bool:
        """Check if a Word document seems to be open"""
        tail = path.stem[len(self.LOCK_MARK) :]
        lock = path.with_stem(self.LOCK_MARK + tail)
        if lock.is_file():
            print(f"{path} seems to be open ({lock.name} exists)")
            return True
        return False

    def _mathicize(self) -> bool:
        """Does the heavly lifting on self.doc"""
        worked = False
        if self._find_styles():
            worked = self._italicize_math() or worked
            self._note_suspects()
        worked = self._fix_islands() or worked
        self._check_antidict()

        if self.counts:
            print("Counts:")
            mkw = max(len(key) for key in self.counts)
            for key, count in self._iter_counter(self.counts):
                print(f" {key.ljust(mkw)}  {count}")

        if self.antiwords:
            print("Antidict:")
            for antiword, count in self._iter_counter(self.antiwords):
                print(f" {get_display(antiword)}  {count}")

        return worked

    @classmethod
    def _iter_counter(cls, counter: Counter) -> Iterator[tuple[str, int]]:
        """Helper function to iterate a Counter object"""
        yield from sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )

    def _italicize_math(self) -> bool:
        """Convert text in formulas to italics"""
        for rnode in self._xpath(self.root, self.formula_xpath):
            self._count("considered for italics")
            text = self._rnode_text(rnode)
            relevant = re.search(self.ITALICABLE_RE, text)
            if relevant is None:
                # A dud
                continue

            if relevant.span() == (0, len(text)):
                # The simple case: range == italic
                self._make_italic(rnode)
                self._count("full", rnode)
                self._count("italicized")
                continue

            # This is the difficult case: Need to create duplicates
            idx_prev = 0
            for match in re.finditer(self.ITALICABLE_RE, text):
                (idx_from, idx_to) = match.span()
                if idx_prev < idx_from:
                    addend = self._mknode(rnode, text[idx_prev:idx_from], False)
                    rnode.addprevious(addend)
                    self._count("split", addend)
                if idx_from < idx_to:
                    addend = self._mknode(rnode, text[idx_from:idx_to], True)
                    rnode.addprevious(addend)
                    self._count("part", addend)
                    self._count("split")
                    self._count("italicized")
                idx_prev = idx_to
            if idx_prev < len(text):
                addend = self._mknode(rnode, text[idx_prev:], False)
                rnode.addprevious(addend)
                self._count("split", addend)
            rnode.getparent().remove(rnode)

        return self.counts["italicized"] > 0

    def _fix_islands(self) -> bool:
        """Find islands of LTR whitespace in RTL"""
        for rnode in self._xpath(self.root, self.ISLAND_XPATH):
            # ISLAND_XPATH takes care of these, but I can't read it
            assert self._rnode_text(rnode).isspace()
            assert self._is_rtl(rnode.getnext())
            assert self._is_rtl(rnode.getprevious())

            rprev = rnode.getprevious()
            self._set_rnode_text(rprev, self._rnode_text(rprev) + self._rnode_text(rnode))
            rnode.getparent().remove(rnode)
            self._count("rtlized islands", rprev)
        return self.counts["rtlized"] > 0

    def _note_suspects(self):
        """Look for text that may be an unmarked formula"""
        for rnode in self._xpath(self.root, self.suspect_xpath):
            self._count("considered for suspect", rnode)
            text = self._rnode_text(rnode)
            if not re.search(self.SUSPECT_RE, text):
                continue

            self._count("suspect", rnode)
            ptext = self._rnode_text(rnode.getprevious())
            ntext = self._rnode_text(rnode.getnext())
            context = "||".join([ptext, text, ntext])
            print(f"You may want to look at '... {context} ...'")

    def _load_antidict(self) -> bool:
        """Load (and test before it's too late) antidict"""
        self.antidict = None

        if not self.args.antidict.is_file():
            return

        with open(self.args.antidict, encoding="utf-8") as fobj:
            antire = "|".join(filter(None, (line.strip() for line in fobj)))
        if not antire:
            return

        try:
            pattern = f"\\b({antire})\\b"
            self.antidict = re.compile(pattern)
        except re.error as exc:
            print(f"Ignoring {self.args.antidict} due to regex error")
            if exc.pos is not None:
                context = pattern[exc.pos - 10 : exc.pos + 10]
                print(f" - {exc}")
                print(f" - Context: {repr(context)}")

    def _check_antidict(self):
        """Look for misspelled words"""
        if self.antidict is None:
            return

        text = "\n".join(
            "".join(tnode.text for tnode in self._xpath(pnode, "./w:r/w:t"))
            for pnode in self._xpath(self.root, "//w:p[w:r/w:t]")
        )
        for match in self.antidict.finditer(text):
            self.antiwords[match.group(0)] += 1

    def _is_rtl(self, rnode) -> bool:
        """Checks whether a <w:r> node is RTL"""
        return self._first(rnode, "./w:rPr/w:rtl") is not None

    def _find_styles(self) -> bool:
        """Find the right styles, set `self.formula_xpath`"""
        with self.izip.open(self.STYLES_IN_ZIP) as ifo:
            styles = etree.parse(ifo).getroot()

        node = self._first(styles, f"//w:style[w:name[@w:val='{self.args.style}']]")
        if node is None:
            print(f'No style named "{self.args.style}" in {self.args.input}')
            return False
        style_id = node.get(self._wtag("styleId"))
        self.formula_xpath = self._FORMULA_XPATH_FORMAT.format(style_id=style_id)

        anti_node = self._first(styles, f"//w:style[w:name[@w:val='{self.args.anti_style}']]")
        if node is not None:
            anti_style_id = anti_node.get(self._wtag("styleId"))
            self.suspect_xpath = self._SUSPECT_XPATH_FORMAT_WITH_ANTI_STYLE.format(
                style_id=style_id,
                anti_style_id=anti_style_id,
            )
        else:
            self.suspect_xpath = self._SUSPECT_XPATH_FORMAT.format(style_id=style_id)
        return True

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

    def _make_italic(self, rnode: etree._Entity):
        """Add the italic tag"""
        self._find(rnode, "w:rPr").append(self._w_i())

    def _count(self, key: str, node: etree._Entity | None = None):
        """Save a comment to be postracted"""
        self.counts[key] += 1
        if node is not None:
            self.comments[key].append(node)

    def _add_comments(self) -> int:
        """Write XML comments for postracted file"""
        n_added = 0
        for message, nodes in self.comments.items():
            comment = f"MATHICHIZE: {message}"
            for node in nodes:
                node.addprevious(etree.Comment(comment))
                n_added += 1
        return n_added

    def _write(self):
        """Create the output .docx"""
        print(f"Writing {self.opath}")
        with ZipFile(self.args.input) as izip, ZipFile(self.opath, "w") as ozip:
            for info in izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    if info.filename == self.DOC_IN_ZIP:
                        ofo.write(etree.tostring(self.doc))
                    else:
                        with izip.open(info, "r") as ifo:
                            ofo.write(ifo.read())

    def _consider_overwrite(self):
        """Carefully overwrite the input file"""
        if self.args.no_overwrite:
            return

        if self._is_open(self.args.input):
            return

        print(f"Press Enter to overwrite {self.args.input}:")
        self._copy(self.opath, self.args.input)
        self.opath = self.args.input  # So we open that one now

    def _copy(self, src: Path | str, dst: Path | str):
        """Wrapper around `shutil.copy`"""
        print(f"{src} -> {dst}")
        shutil.copy(src, dst)

    @classmethod
    def _wtag(cls, tag: str) -> str:
        return f"{{{cls._W}}}{tag}"

    def _w_i(self) -> etree._Entity:
        """Create <w:i> node"""
        return self.root.makeelement(self._wtag("i"))

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

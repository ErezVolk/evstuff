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

from bidi.algorithm import get_display
from lxml import etree

from docx_worker import DocxWorker

# TODO: Hebrew Maqaf


class Proof(DocxWorker):
    """Checks things in .docx files."""

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser(description=self.__class__.__doc__)
        parser.add_argument("-i", "--input", type=Path, help="Input .docx")
        parser.add_argument(
            "-o", "--outdir", type=Path, help="Output directory"
        )
        parser.add_argument(
            "-d",
            "--antidict",
            type=Path,
            default="antidict.txt",
            help=(
                "File with one regex per line"
                " which should NOT be in the text"
            ),
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
            "-S",
            "--anti-style",
            default="לא נוסחה",
            help="Style name for non-formulas",
        )
        parser.add_argument(
            "-D",
            "--dict-style",
            default="מְנֻקָּד",
            help="Style name for anti-spellcheck style",
        )
        parser.add_argument(
            "-R",
            "--rtl-style",
            default="מימין לשמאל",
            help="Style name for forced RTL",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Work even if output file is currently open",
        )
        parser.add_argument(
            "--open",
            action="store_true",
            help="Open output file after processing",
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

    TOTAL_ITALICIZED_KEY = "italicized (total)"
    ITALICABLE_RE = (  # Must work in XPath
        r"\b([A-Z]?[A-Z]?[a-z][A-Za-z]*|[A-Z][A-Z]?)\b"
    )
    SUSPECT_RE = r"(^\s*[A-Z]\s*$|\bP\()"  # Must work in XPath
    _ITALICABLE_XPATH_FORMAT = (
        "//w:r["
        " w:rPr["
        "  w:rStyle[@w:val='{style_id}']"  # Formula style
        "  and"
        "  not(w:i)"  # Not already italicized
        " ]"
        " and"
        " w:t[re:test(., '" + ITALICABLE_RE + "')]"  # Has italicable bits
        "]"
    )
    _SUSPECT_XPATH_FORMAT = (
        "//w:r["
        " w:rPr["
        "  ("
        "    not(w:rStyle)"
        "    or"
        "    w:rStyle[@w:val!='{style_id}']"
        "  )"  # Not formula style
        "  and"
        "  not(w:rtl)"  # But LTR
        " ]"
        " and"
        " w:t[re:test(., '" + SUSPECT_RE + "')]"  # Formula-like
        "]"
    )
    _SUSPECT_XPATH_FORMAT_WITH_ANTI_STYLE = (
        "//w:r["
        " w:rPr["
        "  ("
        "    not(w:rStyle)"  # Unstyled, OR
        "    or"
        "    w:rStyle["
        "      @w:val!='{style_id}'"  # Not formula style
        "      and"
        "      @w:val!='{anti_style_id}'"  # Nor antiformula style
        "    ]"
        "  )"
        "  and"
        "  not(w:rtl)"  # But LTR
        " ]"
        " and"
        " w:t[re:test(., '" + SUSPECT_RE + "')]"  # Formula-like
        "]"
    )
    WEIRD_LTR_SPACE_XPATH = (
        "//w:r["
        " not(w:rPr/w:rtl)"  # Is LTR text
        "  and"
        " preceding-sibling::*[1][self::w:r[w:rPr/w:rtl and w:t]]"  # Post-RTL
        "  and"
        " following-sibling::*[1][self::w:r[w:rPr/w:rtl and w:t]]"  # Pre-RTL
        "  and"
        " w:t["
        "  @xml:space='preserve'"  # With whitespace at edge
        "   and"
        "   re:test(., '^ +$')"  # Only whitespace
        " ]"
        "]"
    )
    FLIP = str.maketrans("()", ")(")

    antidict: re.Pattern | None
    antiwords: Counter = Counter()
    args: argparse.Namespace
    comments: dict = defaultdict(list)
    formula_style_id: str
    opath: Path

    def pre_work(self) -> Path:
        """Return path to input .docx"""
        self.parse_args()
        return self.args.input

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
            self.args.outdir = Path("proof-out") / now.strftime("%Y%m%d-%H%M")

        self.args.outdir.mkdir(parents=True, exist_ok=True)
        self.opath = self.args.outdir / f"proofed-{self.args.input.stem}.docx"

    def work(self):
        """Work with the open input zip file"""
        self._copy(self.args.input, self.args.outdir / "proof-input.docx")

        with self.izip.open(self.DOC_IN_ZIP) as ifo:
            self.doc = etree.parse(ifo)
            self.root = self.doc.getroot()

        self._save_to("proof-input.xml")

        changed = self._proof()
        if changed:
            self.write(self.opath)
        else:
            print("Nothing changed.")

        self._add_comments()
        self._save_to("proof-output.xml")

        if changed:
            self._consider_overwrite()

        if changed and self.args.open:
            subprocess.run(["open", str(self.opath)], check=False)

    def _save_to(self, name: str):
        """Save the XML in a nice format"""
        output = self.args.outdir / name

        print(f"Saving XML to {output}")
        self.doc.write(output, encoding="utf-8", pretty_print=True)

    def _first(self, node: etree._Entity, expr: str) -> etree._Entity | None:
        """First entity matching xpath"""
        for entity in self.xpath(node, expr):
            return entity
        return None

    @classmethod
    def _find(cls, node: etree._Entity, expr: str) -> etree._Entity:
        """Wrapper for etree.find, with namespaces"""
        return node.find(expr, namespaces=cls._NS)

    def _is_open(self, path: Path) -> bool:
        """Check if a Word document seems to be open"""
        tail = path.stem[len(self.LOCK_MARK):]
        lock = path.with_stem(self.LOCK_MARK + tail)
        if lock.is_file():
            print(f"{path} seems to be open ({lock.name} exists)")
            return True
        return False

    def _proof(self) -> bool:
        """Does the heavly lifting on self.doc"""
        worked = False
        if self.find_formula_style():
            worked = self._fix_rtl_formulas() or worked
            worked = self._italicize_math() or worked
            worked = self._nbspize_math() or worked
            self._note_suspects()
        worked = self._fix_weird_ltr_spaces() or worked
        worked = self._force_rtl_islands() or worked
        self._check_antidict()
        self._scan_images()

        self.dump_counter("Counts", self.counts)
        self.dump_counter("Antidict", self.antiwords, get_display)

        return worked

    def _italicize_math(self) -> bool:
        """Convert text in formulas to italics"""
        italicable_xpath = self._ITALICABLE_XPATH_FORMAT.format(
            style_id=self.formula_style_id
        )
        for rnode in self.xpath(self.root, italicable_xpath):
            text = self._rnode_text(rnode)
            relevant = re.search(self.ITALICABLE_RE, text)
            assert relevant is not None  # XPath, but, you know

            if relevant.span() == (0, len(text)):
                # The simple case: range == italic
                self._add_to_rprops(rnode, "i")
                self._count(self.TOTAL_ITALICIZED_KEY)
                self._count("italicized in full")
                continue

            # This is the difficult case: Need to create duplicates
            idx_prev = 0
            for match in re.finditer(self.ITALICABLE_RE, text):
                (idx_from, idx_to) = match.span()
                if idx_prev < idx_from:
                    addend = self._mknode(
                        rnode, text[idx_prev:idx_from], False
                    )
                    rnode.addprevious(addend)
                    self._count("non-italicized part", addend)
                if idx_from < idx_to:
                    addend = self._mknode(rnode, text[idx_from:idx_to], True)
                    rnode.addprevious(addend)
                    self._count("italicized part", addend)
                    self._count(self.TOTAL_ITALICIZED_KEY)
                idx_prev = idx_to
            if idx_prev < len(text):
                addend = self._mknode(rnode, text[idx_prev:], False)
                rnode.addprevious(addend)
                self._count("non-italicized part", addend)
            rnode.getparent().remove(rnode)

        return self.counts[self.TOTAL_ITALICIZED_KEY] > 0

    def _nbspize_math(self) -> bool:
        """Convert regular spaces in formulas to NBSP"""
        expr = (
            f"//w:r["
            f" w:rPr[w:rStyle[@w:val='{self.formula_style_id}']]"  # Formula style
            f"]/w:t[re:test(., ' ')]"  # Contains spaces
        )
        for tnode in self.xpath(self.root, expr):
            tnode.text = tnode.text.replace(" ", "\xA0")
            self._count("nbsp", tnode)

        return self.counts["nbsp"] > 0

    def _fix_weird_ltr_spaces(self) -> bool:
        """Find islands of LTR whitespace in RTL"""
        for rnode in self.xpath(self.root, self.WEIRD_LTR_SPACE_XPATH):
            # WEIRD_LTR_SPACE_XPATH takes care of these, but I can't read it
            assert self._rnode_text(rnode).isspace()
            assert self._is_rtl(rnode.getnext())
            assert self._is_rtl(rnode.getprevious())

            self._add_to_rprops(rnode, "rtl")
            self._count("rtlized spaces", rnode)
        return self.counts["rtlized spaces"] > 0

    def _force_rtl_islands(self) -> bool:
        """Find things which should be forced to be RTL"""
        style_id = self.find_style_id(self.args.rtl_style)
        if not style_id:
            return False
        expr = (
            "//w:r["
            " w:rPr["
            "  w:rtl"  # Is RTL
            "   and"
            "  not(w:rStyle)"  # Unstyled
            " ]"
            "  and"
            " preceding-sibling::*[1][self::w:r[not(w:rPr/w:rtl)]]"  # Post-LTR
            "  and"
            " following-sibling::*[1]["
            "  self::w:r[not(w:rPr/w:rtl)]"  # Pre-LTR
            # "  self::w:r[w:t[re:test(., '^[^א-ת]+$')]]"  # Pre-non-RTL
            " ]"
            "  and"
            " w:t["
            "   re:test(., '^[^א-ת]+$')"  # No directional characters
            " ]"
            "]"
        )
        for rnode in self.xpath(self.root, expr):
            self._add_rstyle(rnode, style_id)
            self._count("force rtl", rnode)
        return self.counts["force rtl"] > 0

    def _fix_rtl_formulas(self):
        """Fix RTL (parts) of formulas"""
        expr = (
            f"//w:r["
            f" w:rPr["
            f"  w:rStyle[@w:val='{self.formula_style_id}']"
            f"  and"
            f"  w:rtl"
            f"]]/w:t[re:test(., '[^ ]')]"
        )
        for tnode in self.xpath(self.doc, expr):
            self._count("rtl formulas", tnode)
            self._count(f"rtl formula: {repr(tnode.text.strip())}")
            tnode.text = tnode.text.translate(self.FLIP)
            rtl = self.find(tnode.getparent(), "./w:rPr/w:rtl")
            rtl.getparent().remove(rtl)
        return self.counts["rtl formulas"] > 0

    def _note_suspects(self):
        """Look for text that may be an unmarked formula"""
        anti_style_id = self.find_style_id(self.args.anti_style)
        if anti_style_id is not None:
            suspect_xpath = self._SUSPECT_XPATH_FORMAT_WITH_ANTI_STYLE.format(
                style_id=self.formula_style_id,
                anti_style_id=anti_style_id,
            )
        else:
            suspect_xpath = self._SUSPECT_XPATH_FORMAT.format(
                style_id=self.formula_style_id
            )

        for rnode in self.xpath(self.root, suspect_xpath):
            self._count("suspect", rnode)
            text = self._rnode_text(rnode)
            assert re.search(self.SUSPECT_RE, text)  # XPath checks, but
            ptext = self._rnode_text(rnode.getprevious())
            ntext = self._rnode_text(rnode.getnext())
            context = "".join([ptext, text, ntext])
            print(f"You may want to look at ... '{context}' ...")

    def _load_antidict(self) -> None:
        """Load (and test before it's too late) antidict"""
        self.antidict = None

        if not self.args.antidict.is_file():
            return

        with open(self.args.antidict, encoding="utf-8") as fobj:
            antire = "|".join(line.strip() for line in fobj if line[0] != "#")
        if not antire:
            return

        pattern = f"\\b({antire})\\b"
        try:
            self.antidict = re.compile(pattern)
        except re.error as exc:
            print(f"Ignoring {self.args.antidict} due to regex error")
            if exc.pos is not None:
                context = pattern[(exc.pos - 10):(exc.pos + 10)]
                print(f" - {exc}")
                print(f" - Context: {repr(context)}")

    def _check_antidict(self):
        """Look for misspelled words"""
        if self.antidict is None:
            return

        style_id = self.find_style_id(self.args.dict_style)
        if style_id:
            t_expr = f"./w:r[not(w:rStyle) or w:rStyle[@w:val!='{style_id}']]/w:t"
        else:
            t_expr = "./w:r/w:t"

        text = "\n".join(
            "".join(tnode.text for tnode in self.xpath(pnode, t_expr))
            for pnode in self.xpath(self.root, "//w:p[w:r/w:t]")
        )
        for match in self.antidict.finditer(text):
            self.antiwords[match.group(0)] += 1

    def _is_rtl(self, rnode) -> bool:
        """Checks whether a <w:r> node is RTL"""
        return self._first(rnode, "./w:rPr/w:rtl") is not None

    def find_formula_style(self) -> bool:
        """Find the formula style"""
        formula_style_id = self.find_style_id(self.args.style)
        if formula_style_id is None:
            print(f'No style named "{self.args.style}" in {self.args.input}')
            return False
        self.formula_style_id = formula_style_id
        return True

    def _mknode(
        self, model: etree._Entity, text: str, italic: bool
    ) -> etree._Entity:
        """Create a duplicate of `model` with different text,
        and possibly italics."""
        rnode = deepcopy(model)
        self._set_rnode_text(rnode, text)
        if italic:
            self._add_to_rprops(rnode, "i")
        return rnode

    def _set_rnode_text(self, rnode: etree._Entity, text: str):
        """Helper to replace <w:t> inside <w:r>"""
        tnode = self._find(rnode, "w:t")
        tnode.text = text
        if text[0].isspace() or text[-1].isspace():
            tnode.set(
                "{http://www.w3.org/XML/1998/namespace}space", "preserve"
            )

    def _count(self, key: str, node: etree._Entity | None = None):
        """Save a comment to be postracted"""
        self.counts[key] += 1
        if node is not None:
            self.comments[key].append(node)

    def _scan_images(self):
        """Count images with/without alt-text"""
        for drawing in self.xpath(
            self.root, "//w:drawing[//a:blip[@r:embed]]"
        ):
            self._count("images")
            for prop in self.xpath(
                drawing, "./wp:inline/wp:docPr[not(@descr)]"
            ):
                self._count("images without alt-text", prop)

    def _add_comments(self) -> int:
        """Write XML comments for postracted file"""
        n_added = 0
        for message, nodes in self.comments.items():
            comment = f"PROOF: {message}"
            for node in nodes:
                node.addprevious(etree.Comment(comment))
                n_added += 1
        return n_added

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

    def _add_rstyle(self, rnode: etree._Entity, style_id: str):
        """Add w:rStyle tag. tag"""
        props = self._find(rnode, "w:rPr")
        if props is None:
            props = self._new_w("rPr")
        props.append(self._new_w("rStyle", attrib={"val": style_id}))

    def _add_to_rprops(self, rnode: etree._Entity, tag: str):
        """Add the italic/rtl/etc. tag"""
        props = self._find(rnode, "w:rPr")
        if props is None:
            props = self._new_w("rPr")
        props.append(self._new_w(tag))

    def _new_w(self, tag: str, attrib: dict[str, str] | None = None) -> etree._Entity:
        """Create <w:*> node"""
        if attrib:
            attrib = {self.wtag(key): val for key, val in attrib.items()}
        return self.root.makeelement(self.wtag(tag), attrib=attrib)

    @classmethod
    def _rnode_text(cls, rnode: etree._Entity) -> str:
        """Return <w:t> node of a <w:r> node"""
        tnode = cls._find(rnode, "w:t")
        if tnode is None:
            return ""
        return tnode.text


if __name__ == "__main__":
    Proof().main()

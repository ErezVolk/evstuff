"""DocxWorker: Base class for scripts that do stuff to .docx files"""
import abc
from collections import Counter
from pathlib import Path
import zipfile

from typing import Callable
from typing import Iterable

from lxml import etree

__all__ = [
    "DocxWorker",
]


class DocxWorker(abc.ABC):
    """Does stuff to .docx files"""
    LOCK_MARK = "~$"
    MAIN_DOC = "document.xml"
    CONTENT_DOCS = [MAIN_DOC, "footnotes.xml"]

    _W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _NS = {
        "w": _W,
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "re": "http://exslt.org/regular-expressions",
    }

    CounterLike = dict[str, int]

    counts: CounterLike = Counter()
    doc: etree._ElementTree  # The "main" document
    docs: dict[str, etree._ElementTree]  # Stem -> content-holding XML tree
    izip: zipfile.ZipFile
    styles: etree._Entity | None = None
    word_folder: zipfile.Path

    @classmethod
    def glob_docs(cls, folder: Path | None = None) -> list[Path]:
        """Find docx files in a folder"""
        if folder is None:
            folder = Path.cwd()
        return [
            path
            for path in folder.glob("*.docx")
            if not path.stem.startswith(cls.LOCK_MARK)
        ]

    def main(self):
        """Main structure of this script"""
        with zipfile.ZipFile(self.pre_work()) as self.izip:
            self.read_content_docs()
            self.work()
        self.post_work()

    @abc.abstractmethod
    def pre_work(self) -> Path:
        """Return path to input .docx"""

    @abc.abstractmethod
    def work(self):
        """Work while `self.izip` is open."""

    def post_work(self):
        """(Optional) work after closing `self.izip`"""

    def read_content_docs(self):
        """Read anything we can find"""
        self.word_folder = zipfile.Path(self.izip, "word/")
        self.docs = {}
        for name in self.CONTENT_DOCS:
            path = self.word_folder / name
            if path.exists():
                self.docs[name] = self.load_word_xml(path)
        self.doc = self.docs[self.MAIN_DOC]

    def load_word_xml(self, path: str | zipfile.Path) -> etree._ElementTree:
        """Parse an XML doc inside the zip"""
        if not isinstance(path, zipfile.Path):
            path = self.word_folder / path
        with path.open() as ifo:
            return etree.parse(ifo)

    def find_style_id(self, name: str) -> str | None:
        """Get a style ID"""
        if self.styles is None:
            self.styles = self.load_word_xml("styles.xml").getroot()

        expr = f"//w:style[w:name[@w:val='{name}']]"
        for node in self.xpath(self.styles, expr):
            return node.get(self.wtag("styleId"))

        return None

    def xpath(self, node: etree._Entity, expr: str) -> Iterable[etree._Entity]:
        """Wrapper for etree.xpath, with namespaces"""
        yield from node.xpath(expr, namespaces=self._NS)

    def doc_xpath(self, expr: str) -> Iterable[etree._Entity]:
        """xpath() for each content document"""
        for doc in self.docs.values():
            yield from self.xpath(doc, expr)

    @classmethod
    def find(cls, node: etree._Entity, expr: str) -> etree._Entity:
        """Wrapper for etree.find, with namespaces"""
        return node.find(expr, namespaces=cls._NS)

    @classmethod
    def wtag(cls, tag: str) -> str:
        """Tag name for "w:tag"."""
        return f"{{{cls._W}}}{tag}"

    def write(self, output_path: Path):
        """Write a copy of the open docx with modified doc"""
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as ozip:
            for info in self.izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    try:
                        ofo.write(etree.tostring(self.docs[info.filename]))
                    except KeyError:
                        with self.izip.open(info, "r") as ifo:
                            ofo.write(ifo.read())

    @classmethod
    def iter_counter(cls, counter: CounterLike) -> Iterable[tuple[str, int]]:
        """Helper function to iterate a Counter object"""
        yield from sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )

    def dump_counter(
        self,
        title: str,
        counter: CounterLike | None = None,
        fmt_key: Callable[[str], str] = lambda key: key,
        sorter: Callable[[CounterLike], Iterable[tuple[str, int]]] | None = None,
    ):
        """Useful for printing summaries"""
        if counter is None:
            counter = self.counts

        if len(counter) == 0:
            return

        if sorter is None:
            sorter = self.iter_counter

        print(f"{title}:")
        mkw = max(len(key) for key in counter)
        for key, count in sorter(counter):
            print(f" {fmt_key(key).ljust(mkw)}  {count}")

    def make_w(self, tag: str, attrib: dict[str, str] | None = None) -> etree._Entity:
        """Create <w:*> node"""
        if attrib:
            attrib = {self.wtag(key): val for key, val in attrib.items()}
        return self.doc.getroot().makeelement(self.wtag(tag), attrib=attrib)

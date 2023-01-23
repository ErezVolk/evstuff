"""DocxWorker: Base class for scripts that do stuff to .docx files"""
import abc
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from typing import Callable
from typing import Iterable

from lxml import etree

__all__ = [
    "DocxWorker",
]


class DocxWorker(abc.ABC):
    """Does stuff to .docx files"""
    LOCK_MARK = "~$"
    DOC_IN_ZIP = "word/document.xml"
    STYLES_IN_ZIP = "word/styles.xml"

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
    doc: etree._ElementTree
    izip: ZipFile
    root: etree._Entity
    styles: etree._Entity | None = None

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
        with ZipFile(self.pre_work()) as self.izip:
            self.doc = self.load_xml(self.DOC_IN_ZIP)
            self.root = self.doc.getroot()
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

    def load_xml(self, path_in_zip: str) -> etree._ElementTree:
        """Parse an XML doc inside the zip"""
        with self.izip.open(path_in_zip) as ifo:
            return etree.parse(ifo)

    def find_style_id(self, name: str) -> str | None:
        """Get a style ID"""
        if self.styles is None:
            self.styles = self.load_xml(self.STYLES_IN_ZIP).getroot()

        expr = f"//w:style[w:name[@w:val='{name}']]"
        for node in self.xpath(self.styles, expr):
            return node.get(self.wtag("styleId"))

        return None

    def xpath(self, node: etree._Entity, expr: str) -> Iterable[etree._Entity]:
        """Wrapper for etree.xpath, with namespaces"""
        yield from node.xpath(expr, namespaces=self._NS)

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
        with ZipFile(output_path, "w") as ozip:
            for info in self.izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    if info.filename == self.DOC_IN_ZIP:
                        ofo.write(etree.tostring(self.doc))
                    else:
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

"""DocxWorker: Base class for scripts that do stuff to .docx files"""
import abc
from pathlib import Path
from zipfile import ZipFile

from typing import Iterator

from lxml import etree


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
        with ZipFile(self.get_ipath()) as self.izip:
            self.doc = self.load_xml(self.DOC_IN_ZIP)
            self.root = self.doc.getroot()
            self.work_with_doc()
        self.work_after_doc()

    @abc.abstractmethod
    def get_ipath(self) -> Path:
        """Return path to input .docx"""

    @abc.abstractmethod
    def work_with_doc(self):
        """Work while `self.izip` is open."""

    def work_after_doc(self):
        """(Optional) work after closing `self.izip`"""

    def load_xml(self, path_in_zip: str) -> etree._ElementTree:
        """Parse an XML doc inside the zip"""
        with self.izip.open(path_in_zip) as ifo:
            return etree.parse(ifo)

    def find_style_id(self, name: str) -> str:
        """Get a style ID"""
        if self.styles is None:
            self.styles = self.load_xml(self.STYLES_IN_ZIP).getroot()

        for node in self.xpath(self.styles, f"//w:style[w:name[@w:val='{name}']]"):
            return node.get(self.wtag("styleId"))

        raise RuntimeError(f"Style {repr(name)} not found")

    def xpath(self, node: etree._Entity, expr: str) -> Iterator[etree._Entity]:
        """Wrapper for etree.xpath, with namespaces"""
        yield from node.xpath(expr, namespaces=self._NS)

    @classmethod
    def wtag(cls, tag: str) -> str:
        return f"{{{cls._W}}}{tag}"

    def write(self, output_path: Path):
        """Write the open docx with modified doc"""
        with ZipFile(output_path, "w") as ozip:
            for info in self.izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    if info.filename == self.DOC_IN_ZIP:
                        ofo.write(etree.tostring(self.doc))
                    else:
                        with self.izip.open(info, "r") as ifo:
                            ofo.write(ifo.read())

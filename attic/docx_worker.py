"""DocxWorker: Base class for scripts that do stuff to .docx files."""
import abc
import typing as t
import zipfile as zf
from collections import Counter
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from pathlib import PurePosixPath

from lxml import etree

__all__ = [
    "DocxWorker",
]

type XPathable = etree._Element | etree._ElementTree  # noqa: SLF001


class DocxWorker(abc.ABC):
    """Do stuff to .docx files."""

    LOCK_MARK = "~$"
    MAIN_STEM = "document"
    CONTENT_STEMS = (MAIN_STEM, "footnotes")
    WORD_FOLDER = "word"

    _W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _OXML = "http://schemas.openxmlformats.org"
    _NS: t.ClassVar[dict[str, str]] = {
        "w": _W,
        "a": _OXML + "/drawingml/2006/main",
        "r": _OXML + "/officeDocument/2006/relationships",
        "wp": _OXML + "/drawingml/2006/wordprocessingDrawing",
        "re": "http://exslt.org/regular-expressions",
    }

    type CounterLike = dict[str, int]
    type Sorter = Callable[[CounterLike], Iterable[tuple[str, int]]]

    counts: CounterLike
    doc: etree._ElementTree  # The "main" document
    docs: dict[str, etree._ElementTree]  # Stem -> content-holding XML tree
    izip: zf.ZipFile
    word_folder: zf.Path
    _styles: etree._Element | None = None

    @classmethod
    def glob_docs(cls, folder: Path | None = None) -> list[Path]:
        """Find docx files in a folder."""
        if folder is None:
            folder = Path.cwd()
        return [
            path
            for path in folder.glob("*.docx")
            if not path.stem.startswith(cls.LOCK_MARK)
        ]

    def main(self) -> None:
        """Script entry point."""
        self.counts = Counter()
        with zf.ZipFile(self.pre_work()) as self.izip:
            self.read_content_docs()
            self.work()
        self.post_work()

    @abc.abstractmethod
    def pre_work(self) -> Path:
        """Return path to input .docx."""

    @abc.abstractmethod
    def work(self) -> None:
        """Work while `self.izip` is open."""

    def post_work(self) -> None:
        """Work after closing `self.izip` (optional)."""
        return

    def read_content_docs(self) -> None:
        """Read anything we can find."""
        self.word_folder = zf.Path(self.izip, self.WORD_FOLDER)
        self.docs = {}
        for stem in self.CONTENT_STEMS:
            path = self.in_word_folder(stem)
            if path.exists():
                self.docs[stem] = self.load_word_xml(path)
        self.doc = self.docs[self.MAIN_STEM]

    def load_word_xml(self, path: str | zf.Path) -> etree._ElementTree:
        """Parse an XML doc inside the zip."""
        if not isinstance(path, zf.Path):
            path = self.in_word_folder(path)
        with path.open() as ifo:
            return etree.parse(ifo)

    def in_word_folder(self, stem: str) -> zf.Path:
        """Build a Path pointing to an XML inside the zip."""
        return self.word_folder / f"{stem}.xml"

    @property
    def styles(self) -> etree._Element:
        """Get the styles XML."""
        if self._styles is None:
            self._styles = self.load_word_xml("styles").getroot()
        return self._styles

    def find_style_id(self, name: str) -> str | None:
        """Get a style ID."""
        expr = f"//w:style[w:name[@w:val='{name}']]"
        for node in self.xpath(self.styles, expr):
            return node.attrib.get(self.wtag("styleId"))

        return None

    def xpath(self, node: XPathable, expr: str) -> Iterable[etree._Element]:
        """Wrap for etree.xpath, with namespaces."""
        yield from node.xpath(expr, namespaces=self._NS)

    def doc_xpath(self, expr: str) -> Iterable[etree._Element]:
        """Xpath for each content document."""
        for doc in self.docs.values():
            yield from self.xpath(doc, expr)

    @classmethod
    def find(cls, node: XPathable, expr: str) -> etree._Element | None:
        """Wrap etree.find, with namespaces."""
        return node.find(expr, namespaces=cls._NS)

    @classmethod
    def must_find(cls, node: XPathable, expr: str) -> etree._Element:
        """Wrap etree.find, with namespaces."""
        found = cls.find(node, expr)
        if not found:
            raise RuntimeError(f"Could not find {expr!r}")
        return found

    @classmethod
    def wtag(cls, tag: str) -> str:
        """Tag name for "w:tag"."""
        return f"{{{cls._W}}}{tag}"

    def write(self, output_path: Path) -> None:
        """Write a copy of the open docx with modified doc."""
        with zf.ZipFile(output_path, "w", compression=zf.ZIP_DEFLATED) as ozip:
            for info in self.izip.infolist():
                with ozip.open(info.filename, "w") as ofo:
                    self._write_entry(info, ofo)

    def _write_entry(self, info: zf.ZipInfo, ofo: t.IO) -> None:
        """Write or copy Zip file entry."""
        path = PurePosixPath(info.filename)
        if str(path.parent) == self.WORD_FOLDER and path.stem in self.docs:
            ofo.write(etree.tostring(self.docs[path.stem]))
        else:
            with self.izip.open(info, "r") as ifo:
                ofo.write(ifo.read())

    @classmethod
    def iter_counter(cls, counter: CounterLike) -> Iterable[tuple[str, int]]:
        """Tterate a Counter object."""
        yield from sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )

    def dump_counter(
        self,
        title: str,
        counter: CounterLike | None = None,
        fmt_key: Callable[[str], str] = lambda key: key,
        sorter: Sorter | None = None,
    ) -> None:
        """Print counter (useful for summaries)."""
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

    def make_w(
        self,
        tag: str,
        attrib: dict[str, str] | None = None,
    ) -> etree._Element:
        """Create <w:*> node."""
        if attrib:
            attrib = {self.wtag(key): val for key, val in attrib.items()}
        return self.doc.getroot().makeelement(self.wtag(tag), attrib=attrib)

    R_XPATH = "w:r | w:ins/w:r | w:hyperlink/w:r"
    RT_XPATH = f"({R_XPATH})/w:t"

    def pnode_tnodes(self, pnode: etree._Element) -> Iterable[etree._Element]:
        """Yield every w:r/w:t node in a w:p node."""
        yield from self.xpath(pnode, self.RT_XPATH)

    def pnode_text(self, pnode: etree._Element) -> Iterable[str]:
        """Yield chunks of text."""
        for rnode in self.xpath(pnode, self.R_XPATH):
            for node in self.xpath(rnode, "w:tab | w:t | w:br[not(@*)]"):
                if node.tag == self.wtag("tab"):
                    yield "\t"
                elif node.tag == self.wtag("br"):
                    yield "\n"
                elif node.text:
                    yield node.text

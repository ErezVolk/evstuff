#!/usr/bin/env python3
"""Based on code from https://github.com/fab-jul/parse_dictionaries."""
import itertools
import json
import zlib
from pathlib import Path

import regex as re
from lxml import etree


ROOT = Path(
    "/System/Library/AssetsV2"
    "/com_apple_MobileAsset_DictionaryServices_dictionaryOSX",
)
JSON = Path("hebrew.json")
WRDS = Path("hebrew.words")
TXTS = Path("hebrew.texts")

_NIQQ = "\u05B0-\u05BC\u05C1\u05C2"
_ALPH = "\u05D0-\u05EA"
_GRSH = "\u05F3"
_OTHR = "\u05F3\u05F4"
_ZVOR = "\u05BD\u05BF(4)"
WORD_RE = re.compile(f"[{_ALPH}][{_ALPH}{_NIQQ}{_OTHR}{_ZVOR}]*[{_ALPH}{_NIQQ}{_GRSH}]")
ZVOR_RE = re.compile(f"[{_ZVOR}]")
NIQQ_RE = re.compile(f"[{_NIQQ}]")
BRACKETS_RE = re.compile(r"\[[^\]]+:[^\]]*?\]")


def main() -> None:
    """Get Hebrew words."""
    if JSON.is_file():
        print("Reading parsed dictionary...")
        with JSON.open(encoding="utf8") as fobj:
            entries = json.load(fobj)
    else:
        body = next(ROOT.glob("**/Hebrew.dictionary/Contents/Resources/Body.data"))
        print(f"Parsing {body}...")
        entries = _parse(body)
        with JSON.open("w", encoding="utf8") as fobj:
            json.dump(entries, fobj, ensure_ascii=False)
    print(f"Number of entries: {len(entries)}")

    with TXTS.open("w", encoding="utf8") as fobj:
        words = {}
        for key, xml in entries:
            node = etree.fromstring(xml)

            for label in node.xpath("//span[contains(@class, 'ty_label')]"):
                label.getparent().remove(label)

            bext = etree.tostring(node, encoding="utf-8", method="text")
            text = bext.decode("utf-8")

            fobj.write(text)
            fobj.write("\n\n")

            if "[" in text:
                text = BRACKETS_RE.sub("", text)

            kord = ZVOR_RE.sub("", key)
            for tord in WORD_RE.findall(f"{kord} {text}"):
                if not NIQQ_RE.search(tord):
                    continue
                if tord.startswith("אְ"):
                    print(text)
                    return
                nztord = ZVOR_RE.sub("", tord)
                words.setdefault(nztord, kord)

    print(f"Number of words: {len(words)}")
    with WRDS.open("w", encoding="utf8") as fobj:
        for word, key in sorted(words.items()):
            fobj.write(word)
            fobj.write("\t")
            fobj.write(key)
            fobj.write("\n")


def _parse(dictionary_path: Path) -> list[tuple[str, str]]:
    """Parse Body.data into a list of entries given as key, definition tuples."""
    with dictionary_path.open("rb") as fobj:
        content_bytes = fobj.read()
    total_bytes = len(content_bytes)

    # The first zip file starts at ~100 bytes:
    content_bytes = content_bytes[100:]

    first = True
    entries = []
    for i in itertools.count():
        if not content_bytes:  # Backup condition in case stop is never True.
            break
        try:
            dec = zlib.decompressobj()
            res = dec.decompress(content_bytes)
            new_entries, stop = _split(res, verbose=first)
            entries += new_entries
            if stop:
                break
            if i % 10 == 0:
                bytes_left = len(content_bytes)  # Approximately...
                progress = 1 - bytes_left / total_bytes
                print(
                    f"{progress * 100:.1f}% // "
                    f"{len(entries)} entries parsed // "
                    f"Latest entry: {entries[-1][0]}",
                )
            first = False

            # Set content_bytes to the unused data so we can start the search for the
            # next zip file.
            content_bytes = dec.unused_data

        except zlib.error:  # Current content_bytes is not a zipfile -> skip a byte.
            content_bytes = content_bytes[1:]

    return entries


def _split(input_bytes: bytes, *, verbose: bool) -> tuple[list[tuple[str, str]], bool]:
    """Split `input_bytes` into a list of tuples (name, definition)."""
    printv = print if verbose else lambda *_, **__: ...

    # The first four bytes are always not UTF-8 (not sure why?)
    input_bytes = input_bytes[4:]

    printv("Splitting...")
    printv(f'{"index": <10}', f'{"bytes": <30}', f'{"as chars"}', "-" * 50, sep="\n")

    entries = []
    total_offset = 0
    stop_further_parsing = False

    while True:
        # Find the next newline, which delimits the current entry.
        try:
            next_offset = input_bytes.index(b"\n")
        except ValueError:  # No more new-lines -> no more entries!
            break

        entry_text = input_bytes[:next_offset].decode("utf-8")

        # The final part of the dictionary contains some meta info, which we skip.
        if "fbm_AdvisoryBoard" in entry_text[:1000]:
            print("fbm_AdvisoryBoard detected, stopping...")
            stop_further_parsing = True
            break

        # Make sure we have a valid entry.
        assert entry_text.startswith("<d:entry")
        assert entry_text.endswith("</d:entry>")

        # The name of the definition is stored in the "d:title" attribute,
        # where "d" is the current domain, which we get from the nsmap - the
        # actual attribute will be "{com.apple.blabla}title" (including the
        # curly brackets).
        xml_entry = etree.fromstring(entry_text)
        domain = xml_entry.nsmap["d"]
        key = f"{{{domain}}}title"
        name = xml_entry.get(key)  # Lookup the attribute in the tree.

        entries.append((name, entry_text))

        printv(
            f"{next_offset + total_offset: 10d}",
            f"{input_bytes[next_offset + 1:next_offset + 5]!s:<30}",
            xml_entry.get(key),
        )

        # There is always 4 bytes of chibberish between entries. Skip them
        # and the new lines (for a total of 5 bytes).
        input_bytes = input_bytes[next_offset + 5:]
        total_offset += next_offset
    return entries, stop_further_parsing


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Based on code from https://github.com/fab-jul/parse_dictionaries"""
import itertools
import json
from pathlib import Path
import zlib

from lxml import etree
import regex as re


ROOT = Path(
    "/System/Library/AssetsV2"
    "/com_apple_MobileAsset_DictionaryServices_dictionaryOSX"
)
JSON = Path("hebrew.json")
WRDS = Path("hebrew.words")

_NIQQ = "\u05B0-\u05BC"
_ALPH = "\u05D0-\u05EA"
_OTHR = "\u05F3"
WORD_RE = f"[{_ALPH}][{_NIQQ}][{_ALPH}{_NIQQ}{_OTHR}]*[{_ALPH}{_NIQQ}]"
BRACKETS_RE = r"\[[^\]]+?\]"


def main():
    """Get Hebrew words"""
    if JSON.is_file():
        print("Reading parsed dictionary...")
        with open(JSON, encoding="utf8") as fobj:
            entries = json.load(fobj)
    else:
        body = next(ROOT.glob("**/Hebrew.dictionary/Contents/Resources/Body.data"))
        print(f"Parsing {body}...")
        entries = _parse(body)
        with open(JSON, "w", encoding="utf8") as fobj:
            json.dump(entries, fobj, ensure_ascii=False)
    print(f"Number of entries: {len(entries)}")

    words = {}
    for key, xml in entries:
        node = etree.fromstring(xml)
        bext = etree.tostring(node, encoding="utf-8", method="text")
        text = bext.decode("utf-8")

        if "[" in text:
            text = re.sub(BRACKETS_RE, "", text)

        for tord in re.findall(WORD_RE, text):
            if tord.startswith("אְ"):
                print(text)
                return
            words.setdefault(tord, key)

    print(f"Number of words: {len(words)}")
    with open(WRDS, "w", encoding="utf8") as fobj:
        for word, key in sorted(words.items()):
            fobj.write(word)
            fobj.write("\t")
            fobj.write(key)
            fobj.write("\n")


def _parse(dictionary_path) -> list[tuple[str, str]]:
    """Parse Body.data into a list of entries given as key, definition tuples."""
    with open(dictionary_path, "rb") as fobj:
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
                    f"Latest entry: {entries[-1][0]}"
                )
            first = False

            # Set content_bytes to the unused data so we can start the search for the
            # next zip file.
            content_bytes = dec.unused_data

        except zlib.error:  # Current content_bytes is not a zipfile -> skip a byte.
            content_bytes = content_bytes[1:]

    return entries


def _split(input_bytes, verbose) -> tuple[list[tuple[str, str]], bool]:
    """Split `input_bytes` into a list of tuples (name, definition)."""
    printv = print if verbose else lambda *a, **k: ...

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
            next_offset = input_bytes.index("\n".encode("utf-8"))
        except ValueError:  # No more new-lines -> no more entries!
            break

        entry_text = input_bytes[:next_offset].decode("utf-8")

        # The final part of the dictionary contains some meta info, which we skip.
        # TODO: might only be for the NOAD, so check other dictionaries.
        if "fbm_AdvisoryBoard" in entry_text[:1000]:
            print("fbm_AdvisoryBoard detected, stopping...")
            stop_further_parsing = True
            break

        # Make sure we have a valid entry.
        assert entry_text.startswith("<d:entry") and entry_text.endswith(
            "</d:entry>"
        ), f"ENTRY: {entry_text} \n REM: {input_bytes}"

        # The name of the definition is stored in the "d:title" attribute,
        # where "d" is the current domain, which we get from the nsmap - the
        # actual attribute will be "{com.apple.blabla}title" (including the
        # curly brackets).
        xml_entry = etree.fromstring(entry_text)
        domain = xml_entry.nsmap["d"]
        key = f"{domain}title"
        name = xml_entry.get(key)  # Lookup the attribute in the tree.

        entries.append((name, entry_text))

        printv(
            f"{next_offset + total_offset: 10d}",
            f"{str(input_bytes[next_offset + 1:next_offset + 5]): <30}",
            xml_entry.get(key),
        )

        # There is always 4 bytes of chibberish between entries. Skip them
        # and the new lines (for a total of 5 bytes).
        input_bytes = input_bytes[next_offset + 5:]
        total_offset += next_offset
    return entries, stop_further_parsing


if __name__ == "__main__":
    main()

# Convert word processor files to InDesign tagged text

(WORK IN PROGRESS)

This little Python 3 script converts a word processor file (currently only .docx) into
an InDesign tagged text format.

Currently usable only if you know how to install Python 3, python-lxml, etc.
Not hard at all, but I haven't had time to write a HOWTO or package as an
installer.

Main features:

- You can control a mapping from Word (character/paragraph) styles to InDesign
  styles, including consistently creating style groups in InDesign.

- Importing a tagged text file is _much_ faster in InDesign.

- The siling InDesign script to this will rerun the conversion, so you'll need
  to do the manual conversion only once.


Missing features (highlights):
- Support to preserve manual formatting
- Other source formats (.odt)
- Tables
- Endnotes
- Linked styles
- Comments


(C) 2018 Erez Volk

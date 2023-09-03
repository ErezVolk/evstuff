#!/usr/bin/env python3
"""Split spreads into pages"""
import argparse

import fitz

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", default="ta.pdf")
parser.add_argument("-o", "--output", default="tb.pdf")
parser.add_argument("-r", "--rtl", action="store_true")
args = parser.parse_args()

src = fitz.open(args.input)
doc = fitz.open()  # empty output PDF

MARGIN = 28
MARMARGIN = (MARGIN, MARGIN)

for spage in src:  # for each page in input
    n = spage.number
    r = spage.rect  # input page rectangle
    d = fitz.Rect(spage.cropbox_position,  # CropBox displacement if not
                  spage.cropbox_position)  # starting at (0, 0)

    r = fitz.Rect(r.tl + MARMARGIN, r.br - MARMARGIN)
    if n == 0 or n + 1 == len(src):
        rect_list = [r]
    else:
        center = (r.x0 + r.x1) / 2
        r1 = fitz.Rect(r.tl, fitz.Point(center, r.y1))
        r2 = fitz.Rect(r1.tr, r.br)
        rect_list = [r2, r1] if args.rtl else [r1, r2]

    for rx in rect_list:  # run thru rect list
        rx += d  # add the CropBox displacement
        page = doc.new_page(
            -1,  # new output page with rx dimensions
            width=rx.width,
            height=rx.height,
        )
        page.show_pdf_page(
            page.rect,  # fill all new page with the image
            src,  # input document
            n,  # input page number
            clip=rx,  # which part to use of input page
        )

doc.save(
    args.output,
    garbage=3,  # eliminate duplicate objects
    deflate=True,  # compress stuff where possible
)

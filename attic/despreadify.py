#!/usr/bin/env python3
"""Split spreads into pages"""
import fitz

src = fitz.open("de_balzano_spreads.pdf")
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
        rect_list = [r1, r2]

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
    "ta.pdf",
    garbage=3,  # eliminate duplicate objects
    deflate=True,  # compress stuff where possible
)

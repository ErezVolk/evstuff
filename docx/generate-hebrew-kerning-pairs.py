#!/usr/bin/env python3
from itertools import product
from itertools import chain

ALPHA_ANY = 'אבגדהוזחטיכלמנסעפצקרשת'
ALPHA_FIN = 'ךםןףץ'
PUNCT_BEG = '(['
PUNCT_ANY = '"-=/־–׳״'
PUNCT_FIN = ',.;)]'
# PUNCT_FIN = ',.;)]„”‚’'

KOSHER_PRE = ALPHA_ANY + PUNCT_BEG + PUNCT_ANY
KOSHER_POST = ALPHA_ANY + ALPHA_FIN + PUNCT_ANY + PUNCT_FIN

remaining = [
    x + y
    for x, y in chain(
        product(ALPHA_ANY, ALPHA_ANY + ALPHA_FIN),  # aleph-aleph
        product(ALPHA_ANY + ALPHA_FIN, PUNCT_ANY + PUNCT_FIN),  # kaf (sofit) + minus
        product(PUNCT_BEG + PUNCT_ANY, ALPHA_ANY),  # minus + kaf (sofit)
    )
]

pair = None
lines = ['']

while remaining:
    try:
        pair = next(p for p in remaining if p[0] == lines[-1][-1])
        remaining.remove(pair)

        char = pair[1]
        lines[-1] += char
        if len(lines[-1]) > 60:
            lines.append(char)
    except (IndexError, StopIteration, TypeError):
        pair = remaining.pop(0)
        lines.append(pair)

with open('hebrew-kerning-pairs.idtt.txt', 'w', encoding='UTF-16LE') as fo:
    fo.write('<UNICODE-MAC>\n')
    fo.write('<Version:13.1><FeatureSet:Indesign-R2L>')
    fo.write('<ColorTable:=<Black:COLOR:CMYK:Process:0,0,0,1>>\n')
    for l in lines:
        if l:
            print(l)
            fo.write('<ParaStyle:>')
            fo.write(l)
            fo.write('\n')


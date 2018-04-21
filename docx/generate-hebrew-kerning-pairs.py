#!/usr/bin/env python3
from itertools import product
from itertools import chain

ALPHA_ANY = 'אבגדהוזחטיכלמנסעפצקרשת'
ALPHA_FIN = 'ךםןףץ'
PUNCT_BEG = '(['
PUNCT_ANY = '"-=/־–׳״'
PUNCT_FIN = ',.;)]„”‚’'

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
line = ''

while remaining:
    try:
        pair = next(p for p in remaining if p[0] == pair[1])
        remaining.remove(pair)
        line += pair[1]
    except (StopIteration, TypeError):
        pair = remaining.pop(0)
        line += '\n'
        line += pair

print(line.strip())

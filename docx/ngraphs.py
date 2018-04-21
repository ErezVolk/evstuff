#!/usr/bin/env python3
import sys
from collections import defaultdict

words_fn = sys.argv[1]
output_fns = sys.argv[2:]
nlens = len(output_fns)
lens = list(range(1, nlens + 1))
ngraphs = {
    n: defaultdict(int)
    for n in lens
}

with open(words_fn, 'r', encoding='utf-8') as words:
    for line in words:
        word = line.strip()
        for idx in range(len(word)):
            maxlen = min(nlens, len(word) - idx)
            for n in range(1, maxlen + 1):
                ngraphs[n][word[idx:idx + n]] += 1

for n, fn in enumerate(output_fns, 1):
    with open(fn, 'w', encoding='utf-8') as of:
        stats = ngraphs[n]
        total = float(sum(stats.values()))
        for text, count in sorted(stats.items(), key=lambda item: -item[1]):
            of.write('%s\t%u\t%.02f%%\n' % (text, count, (count * 100) / total))

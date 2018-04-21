#!/usr/bin/env python3
import sys
import re

with open(sys.argv[1], 'r', encoding='utf-8') as inp:
    for line in inp:
        line = line.strip()
        line = re.sub(r'`-="\'׳״־„”‚’', r' ', line)
        line = re.sub(r'[^ אבגדהוזחטיכלמנסעפצקרשתךםןףץ]', r'', line)
        line = re.sub(r'\s+', r' ', line)
        print(line)


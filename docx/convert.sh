#!/bin/bash

./docx-cat 01-inputs/*.docx > 02-plain.txt
./strip.py 02-plain.txt > 03-stripped.txt
cat 03-stripped.txt |sed -e 's/ /\n/g' > 04-words.txt
sort 04-words.txt |uniq -c |sort -k 1nr > 05-wordfreq.txt
./ngraphs.py 04-words.txt 06a-unigraphs.txt 06b-bigraphs.txt 06c-trigraphs.txt

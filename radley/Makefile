.PHONY: all

MARKDOWN=$(wildcard *.md)

all: $(MARKDOWN:%.md=%.pdf)

%.pdf: %.md
	pandoc --pdf-engine xelatex -o $@ $<

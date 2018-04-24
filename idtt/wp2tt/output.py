#!/usr/bin/env python
import collections
import contextlib
import itertools
import logging
import os
import re


class IOutput(object):
    """Interface for things that write InDesign Tagged Text."""

    def define_style(self, style):
        """Add a style definition."""
        raise NotImplementedError()

    def define_text_variable(self, name, value):
        """Add a text variable."""
        raise NotImplementedError()

    def enter_paragraph(self, style=None):
        """Start a paragraph with a specified style."""
        raise NotImplementedError()

    def leave_paragraph(self):
        """Finalize paragraph."""
        raise NotImplementedError()

    def set_character_style(self, style=None):
        """Start a span using a specific character style."""
        raise NotImplementedError()

    def enter_footnote(self):
        """Add a footnote reference and enter the footnote."""
        raise NotImplementedError()

    def leave_footnote(self):
        """Close footnote, go ack to main text."""
        raise NotImplementedError()

    def write_text(self, text):
        """Add some plain text."""
        raise NotImplementedError()


class WhitespaceStripper(IOutput):
    """A proxy IOutput which strips all initial and final whitespace.

    Good foor footnotes.
    """
    def __init__(self, writer):
        self.writer = writer
        self.begun = False
        self.pending = ''

    def define_style(self, style):
        """Add a style definition."""
        return self.writer.define_style(style)

    def define_text_variable(self, name, value):
        """Add a text variable."""
        return self.writer.define_text_variable(name, value)

    def enter_paragraph(self, style=None):
        """Start a paragraph with a specified style."""
        return self.writer.enter_paragraph(style)

    def leave_paragraph(self):
        """Finalize paragraph."""
        return self.writer.leave_paragraph()

    def set_character_style(self, style=None):
        """Start a span using a specific character style."""
        return self.writer.set_character_style(style)

    def enter_footnote(self):
        """Add a footnote reference and enter the footnote."""
        return self.writer.enter_footnote()

    def leave_footnote(self):
        """Close footnote, go ack to main text."""
        return self.writer.leave_footnote()

    def write_text(self, text):
        """Add some plain text."""
        if not self.begun:
            # Trim initial whitespace
            text = re.sub(r'^\s+', r'', text)
            self.begun = bool(text)

        if self.begun:
            # Defer any possibly final whitespace
            parts = re.split(r'(\s+$)', self.pending + text)
            text = parts[0]
            self.pending = parts[1] if len(parts) > 1 else ''

        return self.writer.write_text(text)


class InDesignTaggedTextOutput(contextlib.ExitStack, IOutput):
    def __init__(self, filename, debug=False):
        super().__init__()
        self._filename = filename
        self._styles = []
        self._headers_written = False
        self._shades = collections.defaultdict(itertools.count)
        self._debug = debug

        self._fo = self.enter_context(open(self._filename, 'w', encoding='UTF-16LE'))
        ufo_fn = self._filename + '.utf8'
        if self._debug:
            self._ufo = self.enter_context(open(ufo_fn, 'w', encoding='UTF-8'))
        elif os.path.isfile(ufo_fn):
            os.unlink(ufo_fn)

    def _writeln(self, line=''):
        self._write(line)
        self._write('\n')

    def define_style(self, style):
        """Add a style definition."""
        if style in self._styles:
            return

        if style.parent_style and style.parent_style.used:
            self.define_style(style.parent_style)

        self._styles.append(style)

        if style.next_style and style.next_style.used:
            self.define_style(style.next_style)
        if self._headers_written:
            self._write_style_definition(style)

    def _write_headers(self):
        if self._headers_written:
            return
        self._writeln('<UNICODE-MAC>')
        self._write(r'<Version:13.1>')
        self._write(r'<FeatureSet:Indesign-R2L>')
        self._write(r'<ColorTable:=')
        self._write(r'<Black:COLOR:CMYK:Process:0,0,0,1>')
        self._write(r'<Cyan:COLOR:CMYK:Process:1,0,0,0>')
        self._write(r'<Magenta:COLOR:CMYK:Process:0,1,0,0>')
        self._write(r'<Yellow:COLOR:CMYK:Process:0,0,1,0>')
        self._write(r'>')
        self._writeln()
        for style in self._styles:
            self._write_style_definition(style)
            self._writeln()
        self._headers_written = True

    def _write_style_definition(self, style):
        logging.debug('InDesign: %s', style)
        id_realm = style.realm[:4].capitalize()
        if style.idtt:
            idtt = [style.idtt]
        else:
            fullness = 50.0 + 50.0 / (1.05 ** next(self._shades[style.realm]))

            if style.realm == 'paragraph':
                idtt = [
                    '<pShadingColor:Yellow>',
                    '<pShadingOn:1>',
                    '<pShadingTint:', str(int(100 - fullness)), '>'
                ]
            elif style.realm == 'character':
                idtt = [
                    '<cColor:Magenta>',
                    '<cColorTint:', str(int(fullness)), '>'
                ]

        self._write('<Define')
        self._write(id_realm)
        self._write('Style:')
        self._write(self._idname(style))
        for elem in idtt:
            self._write(elem)

        if style.parent_style and style.parent_style.used:
            self._write('<BasedOn:')
            self._write(self._idname(style.parent_style))
            self._write('>')
        if style.next_style and style.next_style.used:
            self._write('<Nextstyle:')
            self._write(self._idname(style.next_style))
            self._write('>')
        self._write('>')

    def define_text_variable(self, name, value):
        self._write('<DefineTextVariable:')
        self._write_escaped(name)
        self._write('=<TextVarType:CustomText>')
        self._write('<tvString:')
        self._write_escaped(value)
        self._write('>')
        self._write('>')

    def enter_paragraph(self, style=None):
        """Start a paragraph with a specified style."""
        self._write_headers()
        self._set_style('Para', style)

    def _set_style(self, realm, style):
        if style:
            self.define_style(style)
        self._write('<')
        self._write(realm)
        self._write('Style:')
        if style:
            self._write(self._idname(style))
        self._write('>')

    def _idname(self, style):
        return re.sub(r'\s*/\s*', r'\:', style.name)

    def leave_paragraph(self):
        """Finalize paragraph."""
        self._writeln()

    def set_character_style(self, style=None):
        """Start a span using a specific character style."""
        self._set_style('Char', style)

    def enter_footnote(self):
        """Add a footnote reference and enter the footnote."""
        self._write('<FootnoteStart:>')

    def leave_footnote(self):
        """Close footnote, go ack to main text."""
        self._write('<FootnoteEnd:>')

    def write_text(self, text):
        """Add some plain text."""
        self._write_escaped(text)

    def _write_escaped(self, text):
        return self._write(self._escape(text))

    def _escape(self, text):
        return re.sub(r'([<>])', r'\\\1', text)

    def _write(self, string):
        if string:
            self._fo.write(string)
            if self._debug:
                self._ufo.write(string)

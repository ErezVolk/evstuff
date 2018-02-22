# -*- coding: utf-8 -*-
import sys
import os
import random
import re
import subprocess
import itertools
import urllib2
import logging as logger

logger.basicConfig(stream=sys.stdout, level=logger.DEBUG)

import aqt
from aqt.qt import *

try:
    from PyQt5 import QtCore
except ImportError:
    from PyQt4 import QtCore

HERE = os.path.dirname(os.path.abspath(__file__))
CORPORA = [
    os.path.join(HERE, 'sentences_%02d.txt' % nn)
    for nn in (1, 2, 3)
]


class PlayRandomSentence(QDialog):
    def __init__(self, parent, expression=None, meaning=None):
        super(PlayRandomSentence, self).__init__(parent)
        self.saying = None
        self.get_word(expression, meaning)
        self.look_it_up()
        self.create_gui()

    def create_gui(self):
        layout = QGridLayout()
        self.jpn_font = QFont()
        self.jpn_font.setPointSize(36)
        self.eng_font = QFont()
        self.eng_font.setPointSize(18)
        self.setLayout(layout)
        self.setWindowTitle(self.word)

        layout.addWidget(self.mklabel(self.jpn_text, self.jpn_font))

        if self.both and self.eng_text:
            self.eng_label = self.mklabel(self.eng_text, self.eng_font)
            self.hide_eng()
            layout.addWidget(self.eng_label)

        button = QPushButton('More', self)
        layout.addWidget(button)
        self.connect(button, SIGNAL('clicked()'), self.next_clicked)
        button.setFocus()

        self.connect(self, SIGNAL('finished(int)'), self.shut_up)

        self.actions = [self.play_jpn]
        if self.both:
            self.actions.append(self.play_eng)
        self.curr = itertools.cycle(self.actions)

    def showEvent(self, event):
        super(PlayRandomSentence, self).showEvent(event)
        self.play_next()

    def mklabel(self, text, font):
        label = QLabel(text)
        label.setFont(font)
        label.setWordWrap(True)
        return label

    def get_word(self, word, meaning):
        if word or meaning:
            self.word = word
            self.meaning = meaning
            self.both = word and meaning
        else:
            card = aqt.mw.reviewer.card
            note = card.note()
            self.word = note['Expression']
            self.meaning = note['Meaning']
            self.both = aqt.mw.reviewer.state == 'answer'

    def look_it_up(self):
        for corpus in CORPORA:
            if self.try_corpus(corpus):
                return self.found_pair(random.choice(self.matches))

        return self.found_nothing()

    def found_nothing(self):
        self.human = None
        self.jpn_mp3 = None
        self.sid = None
        self.jpn_text = self.word
        self.eng_text = self.meaning

    def found_pair(self, match):
        self.sid = match['sid']
        self.human = match['mp3']
        self.jpn_text = match['jpn']
        self.eng_text = match['eng']
        self.jpn_mp3 = None
        self.tatoeba = None
        if self.human:
            self.jpn_mp3 = self.try_human()
        if self.human and not self.jpn_mp3:
            self.jpn_text = u'⛬' + self.jpn_text

    def try_human(self):
        fn = '%s.mp3' % self.sid
        path = os.path.join(HERE, fn)
        url = 'https://audio.tatoeba.org/sentences/jpn/' + fn

        if os.path.isfile(path):
            return path

        try:
            subprocess.check_output(['/usr/local/bin/wget', '--timeout=2', url, '-O', path])
            return path
        except Exception as ex:
            logger.exception(ex)

        try:
            response = urllib2.urlopen(url, timeout=1)
        except urllib2.URLError as ex:
            logger.exception(ex)
            return None
        if not response:
            logger.info('No response from %s', url)
            return None
        if response.getcode() != 200:
            logger.info('%s => HTTP %s', url, response.getcode())
            response.close()
            return None

        with open(path, 'wb') as f:
            f.write(response.read())
        response.close()

        return path

    def next_clicked(self):
        self.play_next()

    def play_next(self):
        self.shut_up()
        callback = self.curr.next()
        callback()

    def play_jpn(self):
        if self.human and self.jpn_mp3:
            self.play(self.jpn_mp3)
        else:
            self.say(self.jpn_text, random.choice(JPN_VOICES))

    def play_eng(self):
        self.show_eng()
        self.say(self.eng_text, random.choice(ENG_VOICES))

    def hide_eng(self):
        p = self.eng_label.palette()
        self.eng_foreground = p.color(self.eng_label.foregroundRole())
        self.eng_background = p.color(self.eng_label.backgroundRole())
        p.setColor(self.eng_label.foregroundRole(), self.eng_background)
        self.eng_label.setPalette(p)

    def show_eng(self):
        p = self.eng_label.palette()
        p.setColor(self.eng_label.foregroundRole(), self.eng_foreground)
        self.eng_label.setPalette(p)

    def try_corpus(self, corpus):
        try:
            output = subprocess.check_output([
                '/usr/bin/grep',
                self.word,
                corpus
            ])
            output = output.decode('utf-8')
            self.matches = [
                re.match(
                    r'^'
                    r'(?P<sid>\d+)(?P<mp3>[*]?)\t'
                    r'(?P<jpn>.*)\t'
                    r'\d+[*]?'
                    r'\t(?P<eng>.*)'
                    r'$',
                    line
                ).groupdict()
                for line in output.split('\n')
                if line
            ]
        except Exception:
            self.matches = []
        return bool(self.matches)

    def say(self, text, voice):
        if not text or not voice:
            return
        self._say('/usr/bin/say', '-v', voice, text)

    def play(self, path):
        self._say('/usr/local/bin/play', path)

    def _say(self, executable, *args):
        self.saying = QProcess(self)
        self.saying.finished.connect(self.said)
        self.saying.start(executable, args)
        self.saying.waitForStarted()

    def said(self, *args):
        self.saying = None

    def shut_up(self, *args, **kwargs):
        if self.saying:
            self.saying.kill()
            self.saying.waitForFinished()


class ListenForKey(QtCore.QObject):
    def eventFilter(self, _, event):
        if event.type() != QtCore.QEvent.KeyPress:
            return False
        if event.isAutoRepeat():
            return False
        if event.spontaneous():
            return False
        if event.key() != QtCore.Qt.Key_K:
            return False

        if aqt.mw.state == 'deckBrowser':
            expression = u'食中毒'
            meaning = u'concession'
        elif aqt.mw.state == 'review':
            expression = meaning = None
        else:
            return False
        try:
            PlayRandomSentence(aqt.mw, expression, meaning).exec_()
        except Exception as ex:
            logger.exception(ex)
        return True


JPN_VOICES = ['Otoya', 'Kyoko']
ENG_VOICES = ['Alex', 'Daniel']

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: tatoeba english
# TODO: first word in expression
# TODO: Say using awesometts
# TODO: module


"""
TO RELOAD:

In Anki's debug console (ctrl-shift-:)

import sys
from aqt import mw
sys.path.insert(0,mw.pm.addonFolder())
import play_random_sentence
reload(play_random_sentence)
"""

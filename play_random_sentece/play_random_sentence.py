# -*- coding: utf-8 -*-
import os
import random
import re
import subprocess
import itertools
import urllib2

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

        layout.addWidget(self.mklabel(self.jpn, self.jpn_font))

        if self.both and self.eng:
            self.eng_label = self.mklabel(self.eng, self.eng_font)
            self.hide_eng()
            layout.addWidget(self.eng_label)

        self.button = QPushButton('More', self)
        layout.addWidget(self.button)
        self.connect(self.button, SIGNAL('clicked()'), self.clicked)
        self.connect(self, SIGNAL('finished(int)'), self.shut_up)
        self.button.setFocus()

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
        self.jpn = self.word
        self.eng = self.meaning

    def found_pair(self, match):
        self.sid = match['sid']
        self.human = match['mp3']
        self.jpn = match['jpn']
        self.eng = match['eng']
        if self.human:
            self.jpn_mp3 = self.try_human()
        else:
            self.jpn_mp3 = None

    def try_human(self):
        fn = '%s.mp3' % self.sid
        path = os.path.join(HERE, fn)

        if os.path.isfile(path):
            return path

        url = 'https://audio.tatoeba.org/sentences/jpn/' + fn
        try:
            response = urllib2.urlopen(url, timeout=1)
        except urllib2.URLError:
            return None
        if not response:
            return None
        if response.getcode() != 200:
            response.close()
            return None

        with open(path, 'wb') as f:
            f.write(response.read())
        response.close()

        return path

    def clicked(self):
        self.play_next()

    def play_next(self):
        self.shut_up()
        callback = self.curr.next()
        callback()

    def play_jpn(self):
        if self.human and self.jpn_mp3:
            self.play(self.jpn_mp3)
        else:
            self.say(self.jpn, random.choice(JPN_VOICES))

    def play_eng(self):
        self.show_eng()
        self.say(self.eng, random.choice(ENG_VOICES))

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
            output = run('/usr/bin/grep', self.word, corpus)
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


def run(*cmdline):
    return subprocess.check_output(cmdline)


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
            evlog('ERROR: ', repr(ex))
        return True


def evlog(*parts):
    with open('/tmp/erez.log', 'a+') as evl:
        for part in parts:
            evl.write(unicode(part).encode('utf-8'))
        evl.write('\n')


try:
    os.unlink('/tmp/erez.log')
except Exception:
    pass

# JPN_VOICES = get_voices(r'ja_')
JPN_VOICES = ['Otoya', 'Kyoko']
ENG_VOICES = ['Alex', 'Daniel']

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: tatoeba english
# TODO: first word in expression
# TODO: Say using awesometts
# TODO: module

# -*- coding: utf-8 -*-
import os
import random
import re
import subprocess
import itertools
import urllib2
import shutil

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
        self.font = QFont()
        self.font.setPointSize(36)
        self.setLayout(layout)
        self.setWindowTitle(self.word)

        if self.human:
            layout.addWidget(self.mklabel(u'*' + self.jpn))
        else:
            layout.addWidget(self.mklabel(self.jpn))

        if self.both and self.eng:
            self.back_label = self.mklabel()
            layout.addWidget(self.back_label)

        self.button = QPushButton('More', self)
        layout.addWidget(self.button)
        self.connect(self.button, SIGNAL('clicked()'), self.clicked)
        self.connect(self, SIGNAL('finished(int)'), self.shut_up)
        self.button.setFocus()

        self.actions = [self.play_front]
        if self.both:
            self.actions.append(self.play_back)
        self.curr = itertools.cycle(self.actions)

    def showEvent(self, event):
        super(PlayRandomSentence, self).showEvent(event)
        self.play_next()

    def mklabel(self, text=''):
        label = QLabel(text)
        label.setFont(self.font)
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
        self.sid = None
        self.jpn = self.word
        self.eng = self.meaning

    def found_pair(self, match):
        self.sid = match['sid']
        self.human = match['mp3']
        self.jpn = match['jpn']
        self.eng = match['eng']
        if self.human:
            self.front_mp3 = self.try_human()
        else:
            self.front_mp3 = None

    def try_human(self):
        fn = '%s.mp3' % self.sid
        path = os.path.join(HERE, fn)
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

    def play_front(self):
        if self.front_mp3:
            self.play(self.front_mp3)
        else:
            self.say(self.jpn, random.choice(JPN_VOICES))

    def play_back(self):
        self.back_label.setText(self.eng)
        self.say(self.eng, random.choice(ENG_VOICES))

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


def line_to_hit(line):
    m = re.match(r'^(\d+\*?)\t(.*)\t(\d+\*?)\t(.*)$', line)
    return (m.group(2), m.group(4))


def get_voices(lang):
    output = run('/usr/bin/say', '-v', '?')
    return [
        line.split(' ', 1)[0]
        for line in output.split('\n')
        if lang in line
    ]


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

JPN_VOICES = get_voices(r'ja_')
ENG_VOICES = ['Alex', 'Daniel']

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: Cache tatoeba
# TODO: first word in expression
# TODO: Say using awesometts

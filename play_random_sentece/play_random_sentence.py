# -*- coding: utf-8 -*-
import os
import random
import re
import subprocess
import itertools

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
    def __init__(self, parent, expression, meaning):
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

        self.actions = [self.play_front]
        if self.both:
            self.actions.append(self.play_back)
        self.curr = itertools.cycle(self.actions)

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
                m = random.choice(self.matches)
                self.human = m['mp3']
                self.jpn = m['jpn']
                self.eng = m['eng']
                return

        self.human = None
        self.jpn = self.word
        self.eng = self.meaning

    def clicked(self):
        self.shut_up()
        callback = self.curr.next()
        callback()

    def play_front(self):
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
        self.saying = QProcess(self)
        self.saying.finished.connect(self.said)
        self.saying.start('/usr/bin/say', ['-v', voice, text])
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


class PlayerDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super(PlayerDialog, self).__init__(*args, **kwargs)
        layout = QGridLayout()
        self.setLayout(layout)
        self.setWindowTitle('Your title here')
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        layout.addWidget(self.buttonBox, 2, 0, 2, 1)
        self.connect(self.buttonBox, SIGNAL(u"accepted()"), self.accept)
        self.connect(self.buttonBox, SIGNAL(u"rejected()"), self.reject)


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
            word = u'譲歩'
            meaning = u'concession'
        elif aqt.mw.state == 'review':
            word = meaning = None
        else:
            return False
        try:
            PlayRandomSentence(aqt.mw, word, meaning).exec_()
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

# TODO: try https://audio.tatoeba.org/sentences/jpn/4751.mp3 (cached?)
# TODO: show/play English if asked
# TODO: option to only show English
# TODO: first word in expression

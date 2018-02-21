import os
import random
import re
import subprocess

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
    def __init__(self):
        super(PlayRandomSentence, self).__init__()
        self.both = aqt.mw.reviewer.state == 'answer'
        self.get_word()
        self.look_it_up()
        self.create_gui()
        self.play_front()
        # self.play_back()

    def create_gui(self):
        layout = QGridLayout()
        self.font = QFont()
        self.font.setPointSize(24)
        self.setLayout(layout)
        self.setWindowTitle(self.word)

        if self.human:
            layout.addWidget(self.mklabel(u'*' + self.jpn))
        else:
            layout.addWidget(self.mklabel(self.jpn))

        if self.both and self.eng:
            layout.addWidget(self.mklabel(self.eng))

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        layout.addWidget(self.buttonBox)
        self.connect(self.buttonBox, SIGNAL(u"accepted()"), self.accept)
        self.connect(self.buttonBox, SIGNAL(u"rejected()"), self.reject)

    def mklabel(self, text):
        label = QLabel(text)
        label.setFont(self.font)
        return label

    def get_word(self):
        card = aqt.mw.reviewer.card
        note = card.note()
        self.word = note['Expression']
        self.meaning = note['Meaning']

    def look_it_up(self):
        self.human = None
        self.jpn = self.word
        self.eng = self.meaning

        for corpus in CORPORA:
            if self.try_corpus(corpus):
                m = random.choice(self.matches)
                self.human = m['mp3']
                self.jpn = m['jpn']
                self.eng = m['eng']
                return

    def play_front(self):
        say(self.jpn, random.choice(JPN_VOICES))

    def play_back(self):
        if self.both:
            say(self.eng, random.choice(ENG_VOICES))

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
        with open('/tmp/erez.log', 'w') as f:
            f.write(repr(self.matches))
        return bool(self.matches)


def say(text, voice):
    if text and voice:
        # subprocess.call(['/usr/bin/say', '-v', voice, text])
        subprocess.Popen(['/usr/bin/say', '-v', voice, text])


def run_grep(corpus, word):
    try:
        output = run('/usr/bin/grep', word, corpus)
        return [
            line_to_hit(line)
            for line in output.split('\n')
            if line
        ]
    except Exception:
        return []


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
        if aqt.mw.state != 'review':
            return False
        if event.isAutoRepeat():
            return False
        if event.spontaneous():
            return False
        if event.key() != QtCore.Qt.Key_K:
            return False
        try:
            dialog = PlayRandomSentence()
            if dialog.exec_():
                dialog.play_back()
        except Exception as ex:
            with open('/tmp/erez.log', 'w') as f:
                f.write(repr(ex))
        return True


JPN_VOICES = get_voices(r'ja_')
ENG_VOICES = ['Alex', 'Daniel']

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: try https://audio.tatoeba.org/sentences/jpn/4751.mp3 (cached?)
# TODO: show/play English if asked
# TODO: option to only show English

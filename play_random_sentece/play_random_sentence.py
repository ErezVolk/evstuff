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


def play_random_sentence(word):
    dlg = PlayerDialog()
    if not dlg.exec_():
        return

    eng = hits = None

    for level, corpus in zip('abcdefg', CORPORA):
        hits = run_grep(corpus, word)
        if hits:
            break

    if hits:
        jpn, eng = random.choice(hits)
    else:
        jpn = word

    if aqt.mw.reviewer.state != 'answer':
        eng = None

    say(jpn, random.choice(JPN_VOICES))
    say(eng, random.choice(ENG_VOICES))


def say(text, voice):
    if text and voice:
        subprocess.call(['/usr/bin/say', '-v', voice, text])


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
            card = aqt.mw.reviewer.card
            note = card.note()
            expression = note['Expression']
            play_random_sentence(expression)
        except Exception as ex:
            with open('/tmp/erez.log', 'w+') as f:
                f.write(repr(ex))
        return True


JPN_VOICES = get_voices(r'ja_')
ENG_VOICES = get_voices('my name is')

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: https://audio.tatoeba.org/sentences/jpn/4751.mp3 (cached?)

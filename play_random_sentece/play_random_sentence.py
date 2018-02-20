import os
import random
import re
import subprocess

import aqt

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
    global count
    for level, corpus in zip('abcdefg', CORPORA):
        hits = run_grep(corpus, word)
        if hits:
            break

    if not hits:
        return

    jpn, eng = random.choice(hits)
    subprocess.call(['/usr/bin/say', '-v', random.choice(JPN_VOICES), jpn])
    subprocess.call(['/usr/bin/say', '-v', random.choice(ENG_VOICES), eng])


def run_grep(corpus, word):
    output = run('/usr/bin/grep', word, corpus)
    return [
        line_to_hit(line)
        for line in output.split('\n')
        if line
    ]


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
        if aqt.mw.state != 'review':
            return False
        if aqt.mw.reviewer.state != 'answer':
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
        except Exception:
            pass
        return True


JPN_VOICES = get_voices(r'ja_')
ENG_VOICES = get_voices('my name is') + get_voices('nice to have')

aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

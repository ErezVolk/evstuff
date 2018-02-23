# -*- coding: utf-8 -*-
import aqt

from .logger import logger
from .play_random_sentence import PlayRandomSentence

try:
    from PyQt5 import QtCore
except ImportError:
    from PyQt4 import QtCore


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
            card = aqt.mw.reviewer.card
            note = card.note()
            expression = note['Expression']
            meaning = note['Meaning'] if aqt.mw.reviewer.state == 'answer' else None
        else:
            return False
        try:
            PlayRandomSentence(aqt.mw, expression, meaning).exec_()
        except Exception as ex:
            logger.exception(ex)
        return True


def start():
    aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))

# TODO: first word in expression
# TODO: Say using awesometts
# TODO: Look for kana?
# TODO: play highlighted word
# TODO: run CLI


"""
TO RELOAD:

In Anki's debug console (ctrl-shift-:)

import sys
from aqt import mw
sys.path.insert(0,mw.pm.addonFolder())
import play_random_sentence
reload(play_random_sentence)
"""

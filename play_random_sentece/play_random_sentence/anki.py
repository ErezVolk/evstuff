import aqt

from .logger import logger
from .play_random_sentence import PlayRandomSentence

from PyQt5 import QtCore


class ListenForKey(QtCore.QObject):
    def eventFilter(self, _, event):
        try:
            if event.type() != QtCore.QEvent.KeyPress:
                return False
            if event.isAutoRepeat():
                aqt.utils.showInfo('EREZ EREZ: AutoRepeat')
                return False
            if event.spontaneous():
                aqt.utils.showInfo('EREZ EREZ: Spontaneous')
                return False
            if event.key() != QtCore.Qt.Key_K:
                return False
            if aqt.mw.state != 'review':
                aqt.utils.showInfo('EREZ EREZ: Not review')
                return False

            card = aqt.mw.reviewer.card
            note = card.note()
            if not all(f in note for f in ('Expression', 'Meaning')):
                return False

            expression = note['Expression']
            if aqt.mw.reviewer.state == 'answer':
                meaning = note['Meaning']
            else:
                meaning = None

            PlayRandomSentence(aqt.mw, expression, meaning).exec_()
            return True
        except Exception as ex:
            logger.exception(ex)
            return False


def initialize():
    # aqt.mw.installEventFilter(ListenForKey(parent=aqt.mw))
    oldHandler = aqt.mw.eventFilter

    newObject = ListenForKey(parent=aqt.mw)

    def newHandler(obj, event):
        if not newObject.eventFilter(obj, event):
            return oldHandler(obj, event)

    aqt.mw.eventFilter = newHandler




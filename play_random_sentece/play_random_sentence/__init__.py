#  def start():
#      from .anki import initialize
#      initialize()
import aqt
from anki.hooks import addHook
from .play_random_sentence import PlayRandomSentence


def onK():
    card = aqt.mw.reviewer.card
    note = card.note()
    if not all(f in note for f in ('Expression', 'Meaning')):
        return

    expression = note['Expression']
    if aqt.mw.reviewer.state == 'answer':
        meaning = note['Meaning']
    else:
        meaning = None

    PlayRandomSentence(aqt.mw, expression, meaning).exec_()


def shortcutHook(shortcuts):
    shortcuts.append(('k', onK))


addHook('reviewStateShortcuts', shortcutHook)

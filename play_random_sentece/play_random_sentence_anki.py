#!/usr/bin/env python

if __name__ == '__main__':
    import sys
    from play_random_sentence.play_random_sentence import PlayRandomSentence
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        from PyQt4.QtGui import QApplication

    application = QApplication(sys.argv)
    for expression in sys.argv[1:]:
        prs = PlayRandomSentence(expression=expression, meaning='Damned if I know')
        prs.exec_()
    sys.exit(0)

from play_random_sentence import start
start()

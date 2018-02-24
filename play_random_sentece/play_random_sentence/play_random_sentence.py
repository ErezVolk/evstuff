import os
import random
import re
import subprocess
import itertools

from .logger import logger

try:
    import urllib2
except ImportError:
    urllib2 = None

try:
    import requests
except ImportError:
    requests = None

try:
    from PyQt5 import Qt
except ImportError:
    from PyQt4 import Qt


HERE = os.path.dirname(os.path.abspath(__file__))
CORPORA = [
    os.path.join(HERE, 'sentences_%02d.txt' % nn)
    for nn in (1, 2, 3)
]


class Side(object):
    def __init__(self, lang, voices):
        self.lang = lang
        self.voices = list(voices)
        self.font = Qt.QFont()
        self.human = None
        self.mp3 = None
        self.text = None
        self.sid = None
        self.index = None

    def humanize_font(self):
        if not self.human:
            return
        if self.mp3:
            self.font.setBold(True)
        else:
            self.font.setItalic(True)

    def from_match(self, match):
        self.text = match[self.lang]
        self.sid = match['%s_sid' % self.lang]
        self.human = match['%s_mp3' % self.lang]

    def next_voice(self):
        if self.index is None:
            random.shuffle(self.voices)
            self.index = 0
        self.index = self.index + 1
        return self.voices[self.index % len(self.voices)]


class PlayRandomSentence(Qt.QDialog):
    JPN_VOICES = []
    ENG_VOICES = []
    BLACKLIST = ['Fred', 'Kathy', 'Vicki', 'Victoria']

    def __init__(self, parent=None, expression=None, meaning=None):
        super(PlayRandomSentence, self).__init__(parent)
        self.get_voices()
        self.saying = None
        self.jpn = Side('jpn', self.JPN_VOICES)
        self.eng = Side('eng', self.ENG_VOICES)
        self.get_word(expression, meaning)
        self.look_it_up()
        self.create_gui()

    @classmethod
    def get_voices(cls):
        cls.JPN_VOICES = cls.JPN_VOICES or cls.get_lang_voices('ja') or ['Kyoko', 'Otoyoa']
        cls.ENG_VOICES = cls.ENG_VOICES or cls.get_lang_voices('en') or ['Daniel', 'Samantha']

    @classmethod
    def get_lang_voices(cls, lang):
        all_lang_voices = cls.get_lang_voices_with_voices(lang) or cls.get_lang_voices_with_say(lang)
        return [
            voice
            for voice in all_lang_voices
            if voice not in cls.BLACKLIST
        ]

    @classmethod
    def get_lang_voices_with_voices(cls, lang):
        try:
            output = cls.run('/usr/local/bin/voices', '-l', lang)
            return [
                line.split(' ', 1)[0]
                for line in output.split('\n')
                if ' ' in line
            ]
        except Exception:
            return []

    @classmethod
    def get_lang_voices_with_say(cls, lang):
        try:
            output = cls.run('say', '-v', '?')
            return [
                line.split(' ', 1)[0]
                for line in output.split('\n')
                if ' %s_' % lang in line
            ]
        except Exception:
            return []

    def create_gui(self):
        layout = Qt.QGridLayout()
        self.jpn.font.setPointSize(36)
        self.jpn.humanize_font()

        self.eng.font.setPointSize(18)
        self.eng.humanize_font()
        self.setLayout(layout)
        self.setWindowTitle(self.word)

        layout.addWidget(self.mklabel(self.jpn))

        if self.both and self.eng.text:
            self.eng_label = self.mklabel(self.eng)
            self.hide_eng()
            layout.addWidget(self.eng_label)

        button = Qt.QPushButton('More', self)
        layout.addWidget(button)
        button.clicked.connect(self.next_clicked)
        button.setFocus()

        self.finished.connect(self.shut_up)

        self.actions = [self.play_jpn]
        if self.both:
            self.actions.append(self.play_eng)
        self.curr = itertools.cycle(self.actions)

    def humanize_font(self, font, human, mp3):
        if not human:
            return
        if mp3:
            font.setBold(True)
        else:
            font.setItalic(True)

    def showEvent(self, event):
        super(PlayRandomSentence, self).showEvent(event)
        self.play_next()

    def mklabel(self, side):
        label = Qt.QLabel(side.text)
        label.setFont(side.font)
        label.setWordWrap(True)
        return label

    def get_word(self, expression, meaning):
        self.word = expression
        self.meaning = meaning
        self.both = expression and meaning

    def look_it_up(self):
        self.matches = []
        for corpus in CORPORA:
            if self.try_corpus(corpus):
                if len(self.matches) > 1:
                    break

        if self.matches:
            return self.found_pair(random.choice(self.matches))
        else:
            return self.found_nothing()

    def found_nothing(self):
        self.jpn.text = self.word
        self.eng.text = self.meaning

    def found_pair(self, match):
        self.jpn.from_match(match)
        self.eng.from_match(match)
        self.jpn.mp3 = self.try_human(self.jpn)
        # self.eng.mp3 = self.try_human(self.eng)

    def try_human(self, side):
        if not side.human:
            return None

        fn = '%s.mp3' % side.sid
        path = os.path.join(HERE, fn)
        url = 'https://audio.tatoeba.org/sentences/%s/%s' % (side.lang, fn)

        if os.path.isfile(path) or self.try_wget(url) or self.try_urllib2(url, path):
            return path

        if os.path.isfile(path):
            os.unlink(path)
        return None

    def try_wget(self, url):
        try:
            self.run('/usr/local/bin/wget', '--timeout=3', url, '-P', HERE)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    def try_urllib2(self, url, path):
        if not urllib2:
            return False

        try:
            response = urllib2.urlopen(url, timeout=1)
        except urllib2.URLError as ex:
            logger.exception(ex)
            return False
        if not response:
            logger.info('No response from %s', url)
            return False
        if response.getcode() != 200:
            logger.info('%s => HTTP %s', url, response.getcode())
            response.close()
            return False

        with open(path, 'wb') as f:
            f.write(response.read())
        response.close()
        return True

    def next_clicked(self):
        self.play_next()

    def play_next(self):
        self.shut_up()
        callback = self.curr.next()
        callback()

    def play_jpn(self):
        if self.jpn.human and self.jpn.mp3:
            return self.play(self.jpn.mp3)
        self.say(self.jpn)

    def play_eng(self):
        self.show_eng()
        if self.eng.human and self.eng.mp3:
            return self.play(self.eng.mp3)
        self.say(self.eng)

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
            output = self.run(
                '/usr/bin/grep',
                self.word,
                corpus
            )
            matches = [
                re.match(
                    r'^'
                    r'(?P<jpn_sid>\d+)(?P<jpn_mp3>[*]?)\t'
                    r'(?P<jpn>.*)\t'
                    r'(?P<eng_sid>\d+)(?P<eng_mp3>[*]?)\t'
                    r'(?P<eng>.*)'
                    r'$',
                    line
                ).groupdict()
                for line in output.split('\n')
                if line
            ]
            if not matches:
                return False
            self.matches.extend(matches)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    @staticmethod
    def run(*args):
        output = subprocess.check_output(args)
        return output.decode('utf-8')

    def say(self, side):
        self._say('/usr/bin/say', '-v', side.next_voice(), side.text)

    def play(self, path):
        self._say('/usr/local/bin/play', path)

    def _say(self, executable, *args):
        self.saying = Qt.QProcess(self)
        self.saying.finished.connect(self.said)
        self.saying.start(executable, args)
        self.saying.waitForStarted()

    def said(self, *args):
        self.saying = None

    def shut_up(self, *args, **kwargs):
        if self.saying:
            self.saying.kill()
            self.saying.waitForFinished()


# TODO: cycle defs
# TODO: run under python3
# TODO: use requests if we have it

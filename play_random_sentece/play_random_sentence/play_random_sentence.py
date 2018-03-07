import os
import random
import re
import subprocess
import itertools
from functools import partial

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


def corpus_fn(lang, corpus_no):
    return os.path.join(HERE, '%s_%02d.txt' % (lang, corpus_no))


def run(*args):
    output = subprocess.check_output(args)
    return output.decode('utf-8')


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
        self.text = match['text']
        self.sid = match['sid']
        self.human = match['mp3']

    def next_voice(self):
        if self.index is None:
            random.shuffle(self.voices)
            self.index = 0
        self.index = self.index + 1
        return self.voices[self.index % len(self.voices)]


class JpnMatch(object):
    def __init__(self, corpus_no, line):
        self.corpus_no = corpus_no
        self.fields = re.match(
            r'^'
            r'(?P<lineno>\d+):'
            r'((?P<sid>\d+)(?P<mp3>[*]?)\t)?'
            r'(?P<text>[^\t]+)'
            r'$',
            line.strip()
        ).groupdict()


class EngMatch(object):
    def __init__(self, jpn_match):
        line = run(
            '/usr/local/bin/sed',
            '%sq;d' % jpn_match.fields['lineno'],
            corpus_fn('eng', jpn_match.corpus_no)
        )

        self.fields = re.match(
            r'^'
            r'((?P<sid>\d+)(?P<mp3>[*]?)\t)?'
            r'(?P<text>[^\t]+)',
            line.strip()
        ).groupdict()


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
        cls.JPN_VOICES = cls.JPN_VOICES or cls.get_lang_voices('ja', ['Kyoko', 'Otoyoa'])
        cls.ENG_VOICES = cls.ENG_VOICES or cls.get_lang_voices('en', ['Daniel', 'Samantha'])

    @classmethod
    def get_lang_voices(cls, lang, default):
        all_lang_voices = cls.get_lang_voices_with_voices(lang) or cls.get_lang_voices_with_say(lang)
        return [
            voice
            for voice in all_lang_voices
            if voice not in cls.BLACKLIST
        ] or default

    @classmethod
    def get_lang_voices_with_voices(cls, lang):
        try:
            output = run('/usr/local/bin/voices', '-l', lang)
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
            output = run('say', '-v', '?')
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
        self.jpn_matches = []
        for corpus_no in range(1, 5):
            if self.try_corpus(corpus_no):
                if len(self.jpn_matches) > 1:
                    break

        if self.jpn_matches:
            return self.found_pair(random.choice(self.jpn_matches))
        else:
            return self.found_nothing()

    def found_nothing(self):
        self.jpn.text = self.word
        self.eng.text = self.meaning

    def found_pair(self, jpn_match):
        eng_match = EngMatch(jpn_match)
        self.jpn.from_match(jpn_match.fields)
        self.eng.from_match(eng_match.fields)
        self.jpn.mp3 = self.try_human(self.jpn)
        # self.eng.mp3 = self.try_human(self.eng)

    def try_human(self, side):
        if not side.human:
            return None

        fn = '%s.mp3' % side.sid
        path = os.path.join(HERE, fn)
        url = 'https://audio.tatoeba.org/sentences/%s/%s' % (side.lang, fn)

        places = [
            partial(os.path.isfile, path),
            partial(self.try_requests, url, path),
            partial(self.try_wget, url),
            partial(self.try_urllib2, url, path),
        ]

        if any(func() for func in places):
            return path

        if os.path.isfile(path):
            os.unlink(path)
        return None

    def try_requests(self, url, path):
        if not requests:
            return False

        try:
            r = requests.get(url, timeout=2)
            r.raise_for_status()
            with open(path, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=1024):
                    fd.write(chunk)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    def try_wget(self, url):
        try:
            run('/usr/local/bin/wget', '--timeout=3', url, '-P', HERE)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    def try_urllib2(self, url, path):
        if not urllib2:
            return False

        try:
            response = urllib2.urlopen(url, timeout=2)
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
        callback = next(self.curr)
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

    def try_corpus(self, corpus_no):
        try:
            output = run(
                '/usr/bin/grep',
                '-n',
                self.word,
                corpus_fn('jpn', corpus_no)
            )

            matches = [
                JpnMatch(corpus_no, line)
                for line in output.split('\n')
                if line
            ]
            if not matches:
                return False
            self.jpn_matches.extend(matches)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

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


# TODO: Config file
# TODO: Config dialog
# TODO: cycle defs
# TODO: Utility to produce sentnces_*.txt (incl. download etc.)
# TODO: TTS using awesometts (w/ voices and groups)
# TODO: Play using Anki/awesometts
# TODO: Option: Don't play immediately
# TODO: Option: Don't play English at all

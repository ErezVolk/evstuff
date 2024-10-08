import os
import random
import subprocess
import itertools
from functools import partial

from .logger import logger

try:
    import regex as re
except ImportError:
    import re

try:
    import urllib2
except ImportError:
    urllib2 = None

try:
    import requests
except ImportError:
    requests = None

from PyQt6 import QtCore
from PyQt6 import QtGui
from PyQt6 import QtWidgets


HERE = os.path.dirname(os.path.abspath(__file__))


def corpus_fn(lang, corpus_no):
    return os.path.join(HERE, "%s_%02d.txt" % (lang, corpus_no))


def run(*args):
    output = subprocess.check_output(args)
    return output.decode("utf-8")


class Side(object):
    def __init__(self, lang, voices):
        self.lang = lang
        self.voices = list(voices)
        self.font = QtGui.QFont()
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
        self.text = match["text"]
        self.sid = match["sid"]
        self.human = match["mp3"]

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
            r"^"
            r"(?P<lineno>\d+):"
            r"((?P<sid>\d+)(?P<mp3>[*]?)\t)?"
            r"(?P<text>[^\t]+)"
            r"$",
            line.strip(),
        ).groupdict()


class EngMatch(object):
    def __init__(self, jpn_match):
        sed_bin = next(
            path
            for path in ["/usr/local/bin/gsed", "/usr/bin/sed"]
            if os.path.exists(path)
        )
        line = run(
            sed_bin,
            "%sq;d" % jpn_match.fields["lineno"],
            corpus_fn("eng", jpn_match.corpus_no),
        )

        self.fields = re.match(
            r"^" r"((?P<sid>\d+)(?P<mp3>[*]?)\t)?" r"(?P<text>[^\t]+)", line.strip()
        ).groupdict()


class PlayRandomSentence(QtWidgets.QDialog):
    JPN_VOICES = []
    ENG_VOICES = []
    HEB_VOICES = []
    BLACKLIST = ["Fred", "Kathy", "Vicki", "Victoria"]

    def __init__(self, parent=None, expression=None, meaning=None, lookup=True):
        super(PlayRandomSentence, self).__init__(parent)
        self.grep_bin = next(
            path
            for path in ["/usr/local/bin/rg", "/usr/bin/grep"]
            if os.path.exists(path)
        )
        self.get_voices()
        self.saying = None
        self.jpn = Side("jpn", self.JPN_VOICES)
        self.eng = Side("eng", self.ENG_VOICES)
        self.heb = Side("heb", self.HEB_VOICES)
        self.get_word(expression, meaning)
        if lookup:
            self.look_it_up()
        else:
            self.found_nothing()
        self.create_gui()

    @classmethod
    def get_voices(cls):
        cls.JPN_VOICES = cls.JPN_VOICES or cls.get_lang_voices(
            "ja", ["Kyoko", "Otoyoa"]
        )
        cls.ENG_VOICES = cls.ENG_VOICES or cls.get_lang_voices(
            "en", ["Daniel", "Samantha"]
        )
        cls.HEB_VOICES = cls.HEB_VOICES or cls.get_lang_voices("he", ["Carmit"])

    @classmethod
    def get_lang_voices(cls, lang, default):
        if lang == "en":
            look_for = "Hello, my name is"
        else:
            look_for = f"{lang}_"
        voices = cls.get_lang_voices_with_say(look_for)
        return voices or default

    @classmethod
    def get_lang_voices_with_voices(cls, lang):
        try:
            output = run("/usr/local/bin/voices", "-l", lang)
            return [line.split(" ", 1)[0] for line in output.split("\n") if " " in line]
        except Exception:
            return []

    @classmethod
    def get_lang_voices_with_say(cls, look_for):
        try:
            output = run("say", "-v", "?")
            return [
                line.split(" ", 1)[0]
                for line in output.split("\n")
                if look_for in line
            ]
        except Exception:
            return []

    def create_gui(self):
        layout = QtWidgets.QGridLayout()
        self.jpn.font.setPointSize(36)
        self.jpn.humanize_font()

        self.ans.font.setPointSize(18)
        self.ans.humanize_font()
        self.setLayout(layout)
        self.setWindowTitle(self.word)

        layout.addWidget(self.mklabel(self.jpn))

        if self.both and self.ans.text:
            self.ans_label = self.mklabel(self.ans)
            self.hide_ans()
            layout.addWidget(self.ans_label)

        button = QtWidgets.QPushButton("More", self)
        layout.addWidget(button)
        button.clicked.connect(self.next_clicked)
        button.setFocus()

        self.finished.connect(self.shut_up)

        self.actions = [self.play_jpn]
        if self.both:
            self.actions.append(self.play_ans)
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
        label = QtWidgets.QLabel(side.text)
        label.setFont(side.font)
        label.setWordWrap(True)
        return label

    def get_word(self, expression, meaning):
        self.word = self.strip(expression)
        self.meaning = self.strip(meaning)
        self.both = self.word and self.meaning

    def strip(self, s):
        if not s:
            return s
        return re.sub(r"<.*?>", r"", s)

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
        if self.meaning and re.search(r"[\u05D0-\u05EA]", self.meaning):
            self.ans = self.heb
        else:
            self.ans = self.eng
        self.ans.text = self.meaning

    def found_pair(self, jpn_match):
        # self.setWindowTitle('%s [%s]' % (self.word, len(self.jpn_matches)))
        eng_match = EngMatch(jpn_match)
        self.jpn.from_match(jpn_match.fields)
        self.eng.from_match(eng_match.fields)
        self.jpn.mp3 = self.try_human(self.jpn)
        # self.eng.mp3 = self.try_human(self.eng)
        self.ans = self.eng

    def try_human(self, side):
        if not side.human:
            return None

        fn = "%s.mp3" % side.sid
        path = os.path.join(HERE, fn)
        url = "https://audio.tatoeba.org/sentences/%s/%s" % (side.lang, fn)

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
            with open(path, "wb") as fd:
                for chunk in r.iter_content(chunk_size=1024):
                    fd.write(chunk)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    def try_wget(self, url):
        try:
            run("/usr/local/bin/wget", "--timeout=3", url, "-P", HERE)
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
            logger.info("No response from %s", url)
            return False
        if response.getcode() != 200:
            logger.info("%s => HTTP %s", url, response.getcode())
            response.close()
            return False

        with open(path, "wb") as f:
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

    def play_ans(self):
        self.show_ans()
        if self.ans.human and self.ans.mp3:
            return self.play(self.ans.mp3)
        self.say(self.ans)

    def hide_ans(self):
        p = self.ans_label.palette()
        self.ans_foreground = p.color(self.ans_label.foregroundRole())
        self.ans_background = p.color(self.ans_label.backgroundRole())
        p.setColor(self.ans_label.foregroundRole(), self.ans_background)
        self.ans_label.setPalette(p)

    def show_ans(self):
        p = self.ans_label.palette()
        p.setColor(self.ans_label.foregroundRole(), self.ans_foreground)
        self.ans_label.setPalette(p)

    def try_corpus(self, corpus_no):
        try:
            output = run(self.grep_bin, "-n", self.word, corpus_fn("jpn", corpus_no))

            matches = [JpnMatch(corpus_no, line) for line in output.split("\n") if line]
            if not matches:
                return False
            self.jpn_matches.extend(matches)
            return True
        except Exception as ex:
            logger.exception(ex)
            return False

    def say(self, side):
        self._say("/usr/bin/say", "-v", side.next_voice(), side.text)

    def play(self, path):
        self._say("/usr/local/bin/play", path)

    def _say(self, executable, *args):
        self.saying = QtCore.QProcess(self)
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
# TODO: Utility to produce sentnces_*.txt (incl. download etc.)
# TODO: TTS using awesometts (w/ voices and groups)
# TODO: Play using Anki/awesometts

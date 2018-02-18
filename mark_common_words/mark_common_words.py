# -*- coding: utf-8 -*-
import os
import gzip
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

from anki.hooks import addHook
import aqt


THIS = __file__
HERE = os.path.dirname(THIS)
JMDICT_GZ = os.path.join(HERE, 'JMdict_e.gz')
COMMON_WORDS_PICKLE = os.path.join(HERE, 'common_words.pickle')
WORD_PRIOS_PICKLE = os.path.join(HERE, 'word_prios.pickle')
PICKLE_PROTOCOL = 2  # Highest supported by Python 2.x

# COMMON_PRIOS = ('news1', 'ichi1', 'spec1', 'spec2')
# COMMON_PRIOS = ('spec1', 'spec2', 'nf01', 'nf02', 'nf03', 'nf04')
# COMMON_PRIOS = ('nf01', 'nf02', 'nf03', 'nf04')
COMMON_PRIOS = ('nf01', 'nf02')

word_to_prios = None


def get_word_to_prios():
    global word_to_prios
    if word_to_prios:
        return word_to_prios

    if os.path.isfile(WORD_PRIOS_PICKLE):
        with open(WORD_PRIOS_PICKLE, 'rb') as pickled:
            word_to_prios = pickle.load(pickled)
        return word_to_prios

    jmdict = ET.parse(gzip.GzipFile(JMDICT_GZ)).getroot()
    word_to_prios = {
        k_ele.find('keb').text: [ke_pri.text for ke_pri in k_ele.iter('ke_pri')]
        for k_ele in jmdict.iterfind('entry/k_ele[ke_pri][keb]')
    }

    with open(WORD_PRIOS_PICKLE, 'wb') as pickled:
        pickle.dump(word_to_prios, pickled, PICKLE_PROTOCOL)
    return word_to_prios


def is_common(word):
    prios = get_word_to_prios().get(word)
    return prios and any(prio in prios for prio in COMMON_PRIOS)


def add_browser_menu_entry(browser):
    action = aqt.qt.QAction("Bulk mark ImportantWord", browser)
    browser.connect(action,
                    aqt.qt.SIGNAL("triggered()"),
                    lambda e=browser: bulk_mark_important_word(e))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(action)


def bulk_mark_important_word(browser):
    mark_important_word(browser.selectedNotes())


def mark_important_word(nids):
    aqt.mw.checkpoint("Bulk mark ImportantWord")
    aqt.mw.progress.start()
    for nid in nids:
        note = aqt.mw.col.getNote(nid)
        if "japanese" not in note.model()['name'].lower():
            continue

        if 'Expression' not in note:
            continue

        if 'ImportantWord' not in note:
            continue

        word = aqt.mw.col.media.strip(note['Expression'])
        if not word:
            continue

        if note['ImportantWord'] not in ['', '1']:
            continue  # manually set

        if is_common(word):
            note['ImportantWord'] = '1'
        else:
            note['ImportantWord'] = ''
        note.flush()

    aqt.mw.progress.finish()
    aqt.mw.reset()


addHook("browser.setupMenus", add_browser_menu_entry)

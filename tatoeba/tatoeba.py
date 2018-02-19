#!/usr/bin/env python3
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.ext.declarative

LANGUAGES = ('jpn', 'eng')

Base = sqlalchemy.ext.declarative.declarative_base()


class UserLanguage(Base):
    __tablename__ = 'user_languages'
    _FIELDS = ('lang', 'skill_level', 'username', 'details')
    _NATIVES = set()
    username = sa.Column(sa.String(256), primary_key=True)
    lang = sa.Column(sa.String(256), primary_key=True)
    skill_level = sa.Column(sa.Integer)
    details = sa.Column(sa.String(256))

    @staticmethod
    def want(row):
        if row['skill_level'] != '5':
            return False
        if row['lang'] not in LANGUAGES:
            return False
        UserLanguage._NATIVES.add(row['username'])
        return True


class Sentence(Base):
    __tablename__ = 'sentences_detailed'
    _FIELDS = ('sid', 'lang', 'text', 'username', 'date_added', 'date_modified')
    _SIDS = set()

    sid = sa.Column(sa.Integer, primary_key=True)
    lang = sa.Column(sa.String(8), nullable=False)
    text = sa.Column(sa.Text)
    username = sa.Column(sa.String(256), sa.ForeignKey(UserLanguage.username))
    date_added = sa.Column(sa.String(128))
    date_modified = sa.Column(sa.String(128))

    user_lang = sqlalchemy.orm.relationship('UserLanguage')
    audio = sqlalchemy.orm.relationship('SentenceAudio')

    def __str__(self):
        return '%s%s\t%s' % (self.sid, '*' if self.audio else '', self.text)

    @staticmethod
    def want(row):
        if row['lang'] not in LANGUAGES:
            return False
        Sentence._SIDS.add(row['sid'])
        return True


class UserRating(Base):
    __tablename__ = 'users_sentences'
    _FIELDS = ('username', 'sid', 'rating', 'date_added', 'date_modified')
    username = sa.Column(sa.String(256), primary_key=True)
    sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)
    rating = sa.Column(sa.Integer)
    date_added = sa.Column(sa.String(128))
    date_modified = sa.Column(sa.String(128))

    sentence = sqlalchemy.orm.relationship('Sentence')

    @staticmethod
    def want(row):
        if row['sid'] not in Sentence._SIDS:
            return False
        if row['rating'] != '1':
            return False
        if row['username'] not in UserLanguage._NATIVES:
            return False
        return True


class JpnIndex(Base):
    __tablename__ = 'jpn_indices'
    _FIELDS = ('jp_sid', 'en_sid', 'text')
    jp_sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)
    en_sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)
    text = sa.Column(sa.Text)

    jpn = sqlalchemy.orm.relationship('Sentence', primaryjoin='Sentence.sid==JpnIndex.jp_sid')
    eng = sqlalchemy.orm.relationship('Sentence', primaryjoin='Sentence.sid==JpnIndex.en_sid')

    @staticmethod
    def want(row):
        return row['en_sid'] not in ('0', '-1')


class Link(Base):
    __tablename__ = 'links'
    _FIELDS = ('src_sid', 'dst_sid')
    src_sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)
    dst_sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)

    src = sqlalchemy.orm.relationship('Sentence', primaryjoin='Sentence.sid==Link.src_sid')
    dst = sqlalchemy.orm.relationship('Sentence', primaryjoin='Sentence.sid==Link.dst_sid')

    def __str__(self):
        return '%s->%s' % (self.src_sid, self.dst_sid)

    @staticmethod
    def want(row):
        return row['src_sid'] in Sentence._SIDS and row['dst_sid'] in Sentence._SIDS


class SentenceAudio(Base):
    __tablename__ = 'sentences_with_audio'
    _FIELDS = ('sid', 'username', 'license', 'url')
    _SIDS = set()
    sid = sa.Column(sa.Integer, sa.ForeignKey(Sentence.sid), primary_key=True)
    username = sa.Column(sa.String(256))
    license = sa.Column(sa.String(256))
    url = sa.Column(sa.String(256))

    @staticmethod
    def want(row):
        if row['sid'] in SentenceAudio._SIDS:
            return False
        if row['sid'] not in Sentence._SIDS:
            return False
        if row['username'] not in UserLanguage._NATIVES:
            return False
        SentenceAudio._SIDS.add(row['sid'])
        return True


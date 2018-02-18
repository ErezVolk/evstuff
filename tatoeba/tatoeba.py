#!/usr/bin/env python3
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.ext.declarative

Base = sqlalchemy.ext.declarative.declarative_base()


class Sentence(Base):
    __tablename__ = 'sentences'
    id = sa.Column(sa.Integer, primary_key=True)
    lang = sa.Column(sa.String(8), nullable=False)
    text = sa.Column(sa.Text)


class JpnIndex(Base):
    __tablename__ = 'jpn_indices'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    jp_id = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'))
    en_id = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'))
    text = sa.Column(sa.Text)


class Link(Base):
    __tablename__ = 'links'
    src_id = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'), primary_key=True)
    dst_id = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'), primary_key=True)


class SentenceAudio(Base):
    __tablename__ = 'sentences_with_audio'
    sid = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'), primary_key=True)
    username = sa.Column(sa.String(256))
    license = sa.Column(sa.String(256))
    url = sa.Column(sa.String(256))


class UserLanguage(Base):
    __tablename__ = 'user_languages'
    username = sa.Column(sa.String(256), primary_key=True)
    lang = sa.Column(sa.String(256), primary_key=True)
    skill_level = sa.Column(sa.Integer)
    details = sa.Column(sa.String(256))


class UserRating(Base):
    __tablename__ = 'users_sentences'
    username = sa.Column(sa.String(256), primary_key=True)
    sid = sa.Column(sa.Integer, sa.ForeignKey('sentences.id'), primary_key=True)
    rating = sa.Column(sa.Integer)
    date_added = sa.Column(sa.String(128))
    modified = sa.Column(sa.String(128))

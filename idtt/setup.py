#!/usr/bin/env python3
from setuptools import setup
from wp2tt.version import WP2TT_VERSION

setup(
    name='wp2tt',
    version=WP2TT_VERSION,

    author='Erez Volk',
    author_email='erez.volk@gmail.com',

    packages=['wp2tt'],
    scripts=['bin/wp2tt'],

    install_requires=[
        'attrs',
        'lxml',
    ]
)

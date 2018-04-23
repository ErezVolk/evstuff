#!/usr/bin/env python3
from setuptools import setup
from wp_to_idtt.version import WP_TO_IDTT_VERSION

setup(
    name='wp_to_idtt',
    version=WP_TO_IDTT_VERSION,

    author='Erez Volk',
    author_email='erez.volk@gmail.com',

    packages=['wp_to_idtt'],
    scripts=['bin/wp_to_idtt'],

    install_requires=[
        'attrs',
        'lxml',
    ]
)

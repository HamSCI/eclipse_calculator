#!/usr/bin/env python

from setuptools import setup

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(name='eclipse_calc',
      version='0.15',
      description='Eclipse Obscuation Calculator',
      author='Nathaniel A. Frissell',
      author_email='nathaniel.frissell@scranton.edu',
      url='https://hamsci.org',
      packages=['eclipse_calc'],
      install_requires=requirements
     )

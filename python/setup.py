#!/usr/bin/env python3

from setuptools import setup
import sys
import os

if __name__ == '__main__':
    if sys.argv[1] == 'build-doc': 
        os.system("pdoc3 --html --force src/menshnet")
    elif sys.argv[1] == 'lint':
        os.system("pylint3 -E src/menshnet")
    else:
        setup(
            name='menshnet',
            version='1.0',
            description='Menshnet python client library',
            author='David Schere',
            author_email='dave.avantgarde@gmail.com',
            url='https://menshnet.online/',
            packages=['menshnet'],
            package_dir={'menshnet': 'src/menshnet'},
            install_requires=["paho-mqtt"]
        )



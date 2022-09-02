#!/bin/sh
cp chromedriver /opt/ext/

mkdir -p /opt/ext/python

cp *.py /opt/ext/python
cp -r .venv/* /opt/ext/python
# Remove any symlinks.
find /opt/ext/python -type l -exec rm -f {} \;


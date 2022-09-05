#!/bin/bash
while :
do
  python scraper.py --type='all'
  sleep 86400 # 24 hours
done

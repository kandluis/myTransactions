#!/bin/sh

# Defines the environment variables.
source /Users/nautilik/.zshrc

# Execute the script.
workon myTransactions
python scraper.py
deactivate

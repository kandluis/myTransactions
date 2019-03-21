#!/bin/zsh

# Defines the environment variables.
source /Users/nautilik/.zshrc

# Execute the script.
workon myTransactions
python /home/luis_perez_live/development/myTransactions/scraper.py
deactivate

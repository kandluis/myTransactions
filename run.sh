#!/bin/zsh

# Defines the environment variables.
source /home/luis_perez_live/.zshrc

# Execute the script.
workon transactions
python /home/luis_perez_live/development/myTransactions/scraper.py
deactivate

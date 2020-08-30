#!/bin/zsh

# Defines the environment variables
source ${HOME}/.zshrc
cd ${HOME}/Documents/development/my-transactions

# Execute the script.
workon my-transactions
python scraper.py --type='all' --debug
deactivate

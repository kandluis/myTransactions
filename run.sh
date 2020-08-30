#!/bin/zsh

# Defines the environment variables
source ${HOME}/.zshrc
cd ${HOME}/Documents/development/my-transactions

# Execute the script.
workon my-transactions
rm cookies.pkl
python scraper.py --type='all'
deactivate

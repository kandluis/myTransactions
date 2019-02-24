import mintapi
import os
import pandas as pd
import pygsheets

from typing import NamedTuple

_JOINT_SPENDING_ACCOUNTS = [
    'Spark Visa Signature Business', 'Amazon Card - Luis', 'TOTAL_CHECKING',
    'Citi - Personal', 'Preferred', 'Freedom - Belinda', 'Mariott Rewards',
    'Freedom Unlimited - Belinda', 'Freedom', 'Amazon Store Card'
]
_COLUMNS = ['odate', 'mmerchant', 'amount', 'category']
_COLUMN_NAMES = ['Date', 'Merchant', 'Amount', 'Category']

_RAW_SHEET_TITLE = "Raw - All Transactions"
_KEYS_FILE = 'keys.json'
_WORKSHEET_TITLE = "Transactions Worksheet"

# Paid for Luis' Family's phones are not counted.
# Ignore SCPD Payments.
_IGNORED_MERCHANTS = ['Project Fi', 'Stanford Scpd Ca']
# Credit card payments are redundant.
_IGNORED_CATEGORIES = ['Credit Card Payment']


class ScraperError(Exception):
  pass


class Credentials(NamedTuple):
  email: str
  password: str


def _GetCredentials() -> Credentials:
  """Retrieves the crendentials for logging into Mint.

  This is necessary because they do not currently provide an API.

  Returns:
    The retrieved crendentials
  """
  email = os.environ.get('MINT_EMAIL')
  if not email:
    raise ScraperError("Unable to find email from var %s!" % 'MINT_EMAIL')
  password = os.environ.get('MINT_PASSWORD')
  if not password:
    raise ScraperError("Unable to find pass from var %s!" % 'MINT_PASSWORD')
  return Credentials(email=email, password=password)


def _Normalize(value: str) -> str:
  return ''.join(ch for ch in value if ch.isalnum() or ch.isspace()).title()


def _RetrieveTransactions(creds: Credentials) -> pd.DataFrame:
  """Retrieves all Mint transactions using the given credentials.

  The functions also cleans and prepares the transactions to match
  the format expected by Google sheets.

  Args:
    creds: The Credentials object to use for loging into Mint

  Returns:
    A data frame of all mint transactions"""
  mint = mintapi.Mint(
      creds.email,
      creds.password,
      mfa_method='sms',
      headless=True,
      mfa_input_callback=None)
  transactions = mint.get_detailed_transactions(
      skip_duplicates=True, remove_pending=True)

  spend_transactions = transactions[transactions.account.isin(
      _JOINT_SPENDING_ACCOUNTS) & transactions.isSpending]
  spend_transactions = spend_transactions[_COLUMNS]
  spend_transactions.columns = _COLUMN_NAMES
  spend_transactions.Category = spend_transactions.Category.map(_Normalize)
  spend_transactions.Merchant = spend_transactions.Merchant.map(_Normalize)

  spend_transactions = spend_transactions[~(
      spend_transactions.Category.isin(_IGNORED_CATEGORIES)
      | spend_transactions.Merchant.isin(_IGNORED_MERCHANTS))]
  # Flip expenditures so they're negative.
  spend_transactions.Amount = -1 * spend_transactions.Amount
  return spend_transactions.sort_values('Date', ascending=True)


def _UpdateGoogleSheet(sheet: pygsheets.Spreadsheet,
                       data: pd.DataFrame) -> None:
  """Updates the given transactions sheet with the transactions data

  Args:
    sheet: The sheet containing our transaction analysis and visualization.
    data: The new, cleaned, raw transaction data to analyze.
  """
  all_data_ws = sheet.worksheet_by_title(title=_RAW_SHEET_TITLE)
  all_data_ws.set_dataframe(data, 'A1', fit=True)


def _LoadEnv() -> None:
  if os.path.isfile(".env"):
    with open(".env") as env_file:
      for lin in env_file.readlines():
        name, value = tuple(lin.split("="))
        os.environ[name] = value


def main():
  creds: Credentials = _GetCredentials()
  latestTransactions: pd.DataFrame = _RetrieveTransactions(creds=creds)

  client = pygsheets.authorize(service_file=_KEYS_FILE)
  sheet = client.open(_WORKSHEET_TITLE)
  _UpdateGoogleSheet(sheet=sheet, data=latestTransactions)


if __name__ == '__main__':
  _LoadEnv()
  main()

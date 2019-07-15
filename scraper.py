import argparse
import mintapi  # type: ignore
import os
import pandas as pd  # type: ignore
import pygsheets  # type: ignore

import config

from typing import NamedTuple, Text, Optional

_GLOBAL_CONFIG: config.Config = config.getConfig()


class ScraperError(Exception):
  pass


class Credentials(NamedTuple):
  # The email address associated with the Mint account.
  email: Text
  # The password for the Mint account.
  mintPassword: Text
  # The password for the email account.
  emailPassword: Text


def _GetCredentials() -> Credentials:
  """Retrieves the crendentials for logging into Mint.

  This is necessary because they do not currently provide an API.

  Returns:
    The retrieved crendentials
  """
  email = os.environ.get('MINT_EMAIL')
  if not email:
    raise ScraperError("Unable to find email from var %s!" % 'MINT_EMAIL')
  mintPassword = os.environ.get('MINT_PASSWORD')
  if not mintPassword:
    raise ScraperError("Unable to find pass from var %s!" % 'MINT_PASSWORD')
  emailPassword = os.environ.get('EMAIL_PASSWORD')
  if not emailPassword:
    raise ScraperError("Unable to find pass from var %s!" % 'EMAIL_PASSWORD')
  return Credentials(email=email,
                     mintPassword=mintPassword,
                     emailPassword=emailPassword)


def _Normalize(value: Text) -> Text:
  return ''.join(ch for ch in value if ch.isalnum() or ch.isspace()).title()


def _ConstructArgumentParser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
      description=
      'Scrape mint for transaction data and upload to visualization.')
  parser.add_argument('--debug', action='store_true')
  return parser


class ScraperOptions:
  """Options on how to scrape mint

  Properties:
    showBrowser: bool, property specifying whether to show the brownser
    when logging into mint.
  """

  def __init__(self, showBrowser: Optional[bool] = None) -> None:
    """Initialize an options object

    Args:
      showBrowser: If given, specifies whether to show the browser or not. 
        the default is to show the browser.
    """
    self.showBrowser: bool = False
    if showBrowser is not None:
      self.showBrowser = showBrowser

  @classmethod
  def fromArgs(cls, args: argparse.Namespace) -> 'ScraperOptions':
    """Initializes an options object from the given commandline arguments.showBrowser

    Args:
      args: The parsed arguments from the commandline from which to construct
      these options.
    """
    if args.debug:
      return ScraperOptions(showBrowser=True)
    else:
      return ScraperOptions()


def _RetrieveTransactions(creds: Credentials,
                          options: ScraperOptions) -> pd.DataFrame:
  """Retrieves all Mint transactions using the given credentials.

  The functions also cleans and prepares the transactions to match
  the format expected by Google sheets.

  Args:
    creds: The Credentials object to use for loging into Mint

  Returns:
    A data frame of all mint transactions"""
  mint = mintapi.Mint(creds.email,
                      creds.mintPassword,
                      mfa_method='email',
                      headless=not options.showBrowser,
                      mfa_input_callback=None,
                      session_path=_GLOBAL_CONFIG.SESSION_PATH,
                      imap_account=creds.email,
                      imap_password=creds.emailPassword,
                      imap_server=_GLOBAL_CONFIG.IMAP_SERVER,
                      imap_folder='Inbox')
  transactions = mint.get_detailed_transactions(skip_duplicates=True,
                                                remove_pending=True)

  spend_transactions = transactions[
      transactions.account.isin(_GLOBAL_CONFIG.JOINT_SPENDING_ACCOUNTS)
      & transactions.isSpending]
  spend_transactions = spend_transactions[_GLOBAL_CONFIG.COLUMNS]
  spend_transactions.columns = _GLOBAL_CONFIG.COLUMN_NAMES
  spend_transactions.Category = spend_transactions.Category.map(_Normalize)
  spend_transactions.Merchant = spend_transactions.Merchant.map(_Normalize)

  spend_transactions = spend_transactions[~(
      spend_transactions.Category.isin(_GLOBAL_CONFIG.IGNORED_CATEGORIES)
      | spend_transactions.Merchant.isin(_GLOBAL_CONFIG.IGNORED_MERCHANTS))]
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
  all_data_ws = sheet.worksheet_by_title(title=_GLOBAL_CONFIG.RAW_SHEET_TITLE)
  all_data_ws.set_dataframe(data, 'A1', fit=True)


def _LoadEnv() -> None:
  if os.path.isfile(".env"):
    with open(".env") as env_file:
      for lin in env_file.readlines():
        name, value = tuple(lin.split("="))
        os.environ[name] = value


def main() -> None:
  parser: argparse.ArgumentParser = _ConstructArgumentParser()
  args: argparse.Namespace = parser.parse_args()
  options = ScraperOptions.fromArgs(args)
  creds: Credentials = _GetCredentials()
  print("Retrieving transactions from mint...")
  latestTransactions: pd.DataFrame = _RetrieveTransactions(creds=creds,
                                                           options=options)
  print("Retrieval complete. Uploaded to sheets...")

  client = pygsheets.authorize(service_file=_GLOBAL_CONFIG.KEYS_FILE)
  sheet = client.open(_GLOBAL_CONFIG.WORKSHEET_TITLE)
  _UpdateGoogleSheet(sheet=sheet, data=latestTransactions)
  print("Sheets update complate!")


if __name__ == '__main__':
  _LoadEnv()
  main()

import argparse
import mintapi  # type: ignore
import os
import pandas as pd  # type: ignore
import pygsheets  # type: ignore
import socket
import sys

import config
from datetime import datetime

from typing import Any, Callable, Dict, NamedTuple, List, Text, Optional

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
  parser.add_argument(
      '--types',
      type=str,
      help=
      'One of "all", "transactions", or "accounts" to specify what to scrape',
      default='all')
  return parser


class ScraperOptions:
  """Options on how to scrape mint

  Properties:
    showBrowser: bool, property specifying whether to show the brownser
    when logging into mint.
  """

  def __init__(self, types: Text, showBrowser: bool = False) -> None:
    """Initialize an options object

    Args:
      showBrowser: If given, specifies whether to show the browser or not. 
        the default is to show the browser.
    """
    if types.lower() not in ['all', 'accounts', 'transactions']:
      raise ScraperError("Type %s is not valid." % (types))

    self.showBrowser: bool = showBrowser
    self.scrapeTransactions: bool = (True if types.lower() == 'all'
                                     or types.lower() == 'transactions' else
                                     False)
    self.scrapeAccounts: bool = (True if types.lower() == 'all'
                                 or types.lower() == 'accounts' else False)

  @classmethod
  def fromArgs(cls, args: argparse.Namespace) -> 'ScraperOptions':
    """Initializes an options object from the given commandline arguments.showBrowser

    Args:
      args: The parsed arguments from the commandline from which to construct
      these options.
    """
    if args.debug:
      return ScraperOptions(args.types, showBrowser=args.debug)
    else:
      return ScraperOptions(args.types)


def _LogIntoMint(creds: Credentials, options: ScraperOptions) -> mintapi.Mint:
  """Logs into mint and retrieves an active connection.

  Args:
    creds: The credentials for the account to log into.
    options: Options for how to connect.

  Returns:
    The mint connection object.
  """
  mint = mintapi.Mint(creds.email,
                      creds.mintPassword,
                      mfa_method='email',
                      headless=not options.showBrowser,
                      mfa_input_callback=None,
                      session_path=_GLOBAL_CONFIG.SESSION_PATH,
                      imap_account=creds.email,
                      imap_password=creds.emailPassword,
                      imap_server=_GLOBAL_CONFIG.IMAP_SERVER,
                      imap_folder='Inbox',
                      wait_for_sync=_GLOBAL_CONFIG.WAIT_FOR_ACCOUNT_SYNC)
  return mint


def _RetrieveAccounts(mint: mintapi.Mint) -> pd.DataFrame:
  """Retrieves the latest account information.

  Args:
    mint: The mint account from which to retrieve account info.

  Returns:
    DataFrame containing cleaned account information.
  """

  def sign(acc: Dict[Text, Any]) -> int:
    kCreditAccount = 'credit'
    return (-1 if acc['accountType'] == kCreditAccount else 1)

  def getAccountType(originalType: Text) -> Text:
    # Process in sorted order from longest to shortest (more specific ones match first)
    for substring, accountType in sorted(
        _GLOBAL_CONFIG.ACCOUNT_NAME_TO_TYPE_MAP,
        key=lambda x: len(x[0]),
        reverse=True):
      if substring.lower() in originalType.lower():
        return accountType
    print("No account type for account with type: %s" % originalType)
    return 'Unknown - %s' % (originalType)

  accounts: List[Dict[Text, Any]] = mint.get_accounts(get_detail=False)
  return pd.DataFrame([{
      'Name': account['accountName'],
      'Type': getAccountType(account['accountName']),
      'Balance': sign(account) * account['currentBalance']
  } for account in accounts if account['isActive']])
  accounts = accounts[_GLOBAL_CONFIG.ACCOUNT_COLUMN_NAMES]
  return accounts


def _RetrieveTransactions(mint: mintapi.Mint) -> pd.DataFrame:
  """Retrieves all Mint transactions using the given credentials.

  The functions also cleans and prepares the transactions to match
  the format expected by Google sheets.

  Args:
    mint: The mint connection object to the active session.

  Returns:
    A data frame of all mint transactions"""
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
                       transactions: Optional[pd.DataFrame],
                       accounts: Optional[pd.DataFrame]) -> None:
  """Updates the given transactions sheet with the transactions data

  Args:
    sheet: The sheet containing our transaction analysis and visualization.
    data: The new, cleaned, raw transaction data to analyze.
  """
  if transactions is not None:
    all_transactions_ws = sheet.worksheet_by_title(
        title=_GLOBAL_CONFIG.RAW_TRANSACTIONS_TITLE)
    all_transactions_ws.set_dataframe(transactions, 'A1', fit=True)

  if accounts is not None:
    all_accounts_ws = sheet.worksheet_by_title(
        title=_GLOBAL_CONFIG.RAW_ACCOUNTS_TITLE)
    all_accounts_ws.set_dataframe(accounts, 'A1', fit=True)

  settings_ws = sheet.worksheet_by_title(
      title=_GLOBAL_CONFIG.SETTINGS_SHEET_TITLE)
  # Update with current time.
  today = datetime.today()
  today_string = today.strftime('%d-%B-%Y %H:%M:%S %Z')
  hostname = socket.gethostname()
  settings_ws.set_dataframe(pd.DataFrame([today_string, hostname]), 'D2')


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
  print("Logging into mint")
  mint: mintapi.Mint = _LogIntoMint(creds, options)
  print("Connecting to sheets.")
  client = pygsheets.authorize(service_file=_GLOBAL_CONFIG.KEYS_FILE)
  sheet = client.open(_GLOBAL_CONFIG.WORKSHEET_TITLE)

  def messageWrapper(msg: Text, f: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    print(msg)
    sys.stdout.flush()
    return f()

  latestAccounts: pd.DataFrame = (messageWrapper(
      "Retrieving accounts...", lambda: _RetrieveAccounts(mint))
                                  if options.scrapeAccounts else None)
  latestTransactions: pd.DataFrame = (messageWrapper(
      "Retrieving transactions...", lambda: _RetrieveTransactions(mint))
                                      if options.scrapeTransactions else None)

  print("Retrieval complete. Uploading to sheets...")
  _UpdateGoogleSheet(sheet=sheet,
                     transactions=latestTransactions,
                     accounts=latestAccounts)

  print("Sheets update complate!")


if __name__ == '__main__':
  _LoadEnv()
  main()

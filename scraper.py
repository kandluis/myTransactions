import argparse
import config
import dotenv  # type: ignore
import json
import mintapi  # type: ignore
import os
import pandas as pd  # type: ignore
import pickle
import pygsheets  # type: ignore
import socket
import sys
import time

from datetime import datetime

from google.oauth2 import service_account  # type: ignore

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Text,
)

_GLOBAL_CONFIG: config.Config = config.getConfig()


class ScraperError(Exception):
  """Error raised by the scraper when an exception is encountered."""
  pass


class Credentials(NamedTuple):
  """Holds credential information needed to successfully run the scraper.

  Properties:
    email: The email address associated with the Mint account.
    mintPassword: The password for the Mint account.
    emailPassword: The password for the email account.

  """
  email: Text
  mintPassword: Text
  emailPassword: Text


def _GetCredentials() -> Credentials:
  """Retrieves the crendentials for logging into Mint.

  This is necessary because they do not currently provide an API.

  Returns:
    The retrieved crendentials
  """
  email = os.getenv('MINT_EMAIL')
  if not email:
    raise ScraperError("Unable to find email from var %s!" % 'MINT_EMAIL')
  mintPassword = os.getenv('MINT_PASSWORD')
  if not mintPassword:
    raise ScraperError("Unable to find pass from var %s!" % 'MINT_PASSWORD')
  emailPassword = os.getenv('EMAIL_PASSWORD')
  if not emailPassword:
    raise ScraperError("Unable to find pass from var %s!" % 'EMAIL_PASSWORD')
  return Credentials(email=email,
                     mintPassword=mintPassword,
                     emailPassword=emailPassword)


def _Normalize(value: Text) -> Text:
  """Normalizes the text value

  Args:
    value: The text to be normalized.

  Returns:
    The normalized test.
  """
  return ''.join(ch for ch in value if ch.isalnum() or ch.isspace()).title()


def _ConstructArgumentParser() -> argparse.ArgumentParser:
  """Constructs the argument parser for the script."""
  parser = argparse.ArgumentParser(
      description='Scrape mint for transaction data and upload to '
                  'visualization.')
  parser.add_argument('--debug', action='store_true')
  parser.add_argument(
      '--types',
      type=str,
      help='One of "all", "transactions", or "accounts" to specify what to '
           'scrape',
      default='all')
  parser.add_argument(
      '--cookies',
      type=str,
      default=None,
      help='The location of the cookies file to load and also update.')
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
      types: One of 'all', 'accounts', 'transactions' specifying what type of
        data to scrape from Mint.
      showBrowser: If given, specifies whether to show the browser or not.
        the default is to show the browser.
    """
    if types.lower() not in ['all', 'accounts', 'transactions']:
      raise ScraperError("Type %s is not valid." % (types))

    self.showBrowser: bool = showBrowser
    self.scrapeTransactions = (True if types.lower() == 'all' or types.lower() == 'transactions' else False)
    self.scrapeAccounts = (True if types.lower() == 'all' or types.lower() == 'accounts' else False)

  @classmethod
  def fromArgs(cls, args: argparse.Namespace) -> 'ScraperOptions':
    """Initializes an options object from the given commandline
    arguments.showBrowser

    Args:
      args: The parsed arguments from the commandline from which to construct
      these options.
    """
    if args.debug:
      return ScraperOptions(args.types, showBrowser=args.debug)
    else:
      return ScraperOptions(args.types)


def _fetchCookies(cookies_file: Text) -> List[Text]:
  """Fetches the cookies for Mint if available.

  Args:
    cookies_file: The location of the cookies.

  Returns:
    The fetched cookies, if any.
  """
  cookies: List[Text] = []
  if os.path.exists(cookies_file):
    with open(cookies_file, 'rb') as f:
      cookies = pickle.load(f)
  return cookies


def _dumpCookies(mint: mintapi.Mint, cookies_file: Text) -> None:
  """Dumps the cookies in the current session to the cookies file.

  Args:
    mint: The current mint session, already logged in.
    cookies_file: The location of the cookies file.
  """
  with open(cookies_file, 'wb') as f:
    pickle.dump(mint.driver.get_cookies(), f)


def _LogIntoMint(creds: Credentials, options: ScraperOptions,
                 chromedriver_download_path: Text,
                 cookies: List[Text]) -> mintapi.Mint:
  """Logs into mint and retrieves an active connection.

  Args:
    creds: The credentials for the account to log into.
    options: Options for how to connect.
    chromedriver_download_path: Location of chromedriver.
    cookies: Cookies to attach to the session, when provided.

  Returns:
    The mint connection object.
  """
  if os.getenv('CHROME_SESSION_PATH'):
    session_path = os.getenv('CHROME_SESSION_PATH')
  else:
    session_path = os.path.join(os.getcwd(), '.mintapi', 'session')
  if os.getenv('MFA_TOKEN'):
    mfa_method = 'soft-token'
    mfa_token = os.getenv('MFA_TOKEN')
  else:
    mfa_method = 'text'
    mfa_token = None

  mint = mintapi.Mint(creds.email,
                      creds.mintPassword,
                      chromedriver_download_path=chromedriver_download_path,
                      headless=not options.showBrowser,
                      imap_account=creds.email,
                      imap_folder='Inbox',
                      imap_password=creds.emailPassword,
                      imap_server=_GLOBAL_CONFIG.IMAP_SERVER,
                      mfa_input_callback=None,
                      mfa_method=mfa_method,
                      mfa_token=mfa_token,
                      session_path=session_path,
                      wait_for_sync=_GLOBAL_CONFIG.WAIT_FOR_ACCOUNT_SYNC,
                      )
  time.sleep(5)

  # Load cookies if provided. These are cookies only for mint.com domain.
  [mint.driver.add_cookie(cookie) for cookie in cookies]
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
    # Process in sorted order from longest to shortest
    # (more specific ones match first)
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
                                                remove_pending=False,
                                                include_investment=False)

  spend_transactions = transactions[
      (~transactions.account.isin(_GLOBAL_CONFIG.SKIPPED_ACCOUNTS))
      & transactions.isSpending & ~transactions.isTransfer]
  spend_transactions = spend_transactions[_GLOBAL_CONFIG.COLUMNS]
  spend_transactions.columns = _GLOBAL_CONFIG.COLUMN_NAMES
  spend_transactions.Category = spend_transactions.Category.map(_Normalize)
  spend_transactions.Merchant = spend_transactions.Merchant.map(_Normalize)
  spend_transactions.Account = spend_transactions.Account.map(_Normalize)

  spend_transactions = spend_transactions[~(
      spend_transactions.Category.isin(_GLOBAL_CONFIG.IGNORED_CATEGORIES)
      | spend_transactions.Merchant.isin(_GLOBAL_CONFIG.IGNORED_MERCHANTS)
      | spend_transactions.ID.isin(_GLOBAL_CONFIG.IGNORED_TXNS))]
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


def _getGoogleCredentials() -> Optional[service_account.Credentials]:
  """Loads the Google Account Service Credentials to access sheets."""
  credentials_string = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
  if not credentials_string:
    return None
  service_info: Mapping[str, str] = json.loads(credentials_string)
  _SCOPES = ('https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive')
  return service_account.Credentials.from_service_account_info(
      service_info, scopes=_SCOPES)


def main() -> None:
  """Main function for the script."""
  parser: argparse.ArgumentParser = _ConstructArgumentParser()
  args: argparse.Namespace = parser.parse_args()
  options = ScraperOptions.fromArgs(args)
  creds: Credentials = _GetCredentials()

  print("Logging into mint")
  if os.getenv('CHROMEDRIVER_PATH'):
    chromedriver_download_path = os.getenv('CHROMEDRIVER_PATH')
  else:
    chromedriver_download_path = os.getcwd()
  assert chromedriver_download_path

  cookies: List[Text] = []
  if args.cookies:
    cookies_file = os.path.join(chromedriver_download_path, args.cookies)
    cookies = _fetchCookies(cookies_file)

  mint: mintapi.Mint = _LogIntoMint(creds, options, chromedriver_download_path,
                                    cookies)
  if args.cookies:
    _dumpCookies(mint, cookies_file)
  print("Connecting to sheets.")

  client = pygsheets.authorize(custom_credentials=_getGoogleCredentials())
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
  dotenv.load_dotenv()
  main()

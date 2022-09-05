import argparse
import config
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
    sheets: The credentials for the service account for Google Sheets.

  """
  email: str
  mintPassword: str
  emailPassword: str
  sheets: service_account.Credentials


def _getGoogleCredentials() -> service_account.Credentials:
  """Loads the Google Account Service Credentials to access sheets."""
  credentials_string = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
  if not credentials_string:
    raise ScraperError(
        f"Invalid Google credentials. Got {credentials_string}")
  service_info: Mapping[str, str] = json.loads(credentials_string)
  _SCOPES = ('https://www.googleapis.com/auth/spreadsheets',
             'https://www.googleapis.com/auth/drive')
  return service_account.Credentials.from_service_account_info(
      service_info, scopes=_SCOPES)


def _GetCredentials() -> Credentials:
  """Retrieves the crendentials for logging into Mint from the environment.

  This is necessary because they do not currently provide an API.

  Returns:
    The retrieved crendentials
  """
  email = os.getenv('MINT_EMAIL')
  if not email:
    raise ScraperError("Unable to find email from var %s!" % 'MINT_EMAIL')
  mintPassword = os.getenv('MINT_PASSWORD')
  if not mintPassword:
    raise ScraperError("Unable to find pass from var %s!" %
                       'MINT_PASSWORD')
  emailPassword = os.getenv('EMAIL_PASSWORD')
  if not emailPassword:
    raise ScraperError("Unable to find pass from var %s!" %
                       'EMAIL_PASSWORD')
  sheets_creds = _getGoogleCredentials()
  return Credentials(email=email,
                     mintPassword=mintPassword,
                     emailPassword=emailPassword,
                     sheets=sheets_creds)


def _Normalize(value: str) -> str:
  """Normalizes the str value

  Args:
    value: The str to be normalized.

  Returns:
    The normalized str.
  """
  return ''.join(ch for ch in value if ch.isalnum() or ch.isspace()).title()


def _NormalizeMerchant(merchant: str) -> str:
  """Normalizes the str merchant of a merchant.

  Args:
    merchant: The str to be normalized.

  Returns:
    The normalized merchant.
  """
  nChars = 0
  trimmed = []
  for ch in merchant:
    if ch.isalpha() or ch.isspace():
      trimmed.append(ch)
      if ch.isalpha():
        nChars += 1
    if nChars >= _GLOBAL_CONFIG.MAX_MERCHANT_NAME_CHARS:
      break
  normalized = ' '.join(''.join(trimmed).split()).title()
  for simpleName in _GLOBAL_CONFIG.MERCHANT_NORMALIZATION:
    if simpleName in normalized:
      return simpleName
  return normalized


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
      '--cookies_path',
      type=str,
      default=None,
      help='The location of the cookies file to load and also update.')
  return parser


class ScraperOptions:
  """Options on how to scrape mint.

  Properties:
    show_browser: bool, property specifying whether to show the brownser
    when logging into mint.
    scrape_transactions: bool. If true, we scrape txns. Default true.
    scrape_accounts: bool, if true, we scrape account data. Default true.
  """
  # When true, browser head is shown. Useful for debugging.
  show_browser: bool = False
  # When true, scrape txn data from Mint.
  scrape_transactions: bool = True
  # When true, scrape account data from Mint.
  scrape_accounts: bool = True
  # Path where we store the chrome session (speed up scraping).
  session_path: str = os.path.join(os.getcwd(), '.mintapi', 'session')
  # MFA Method to use.
  mfa_method: str = 'str'
  # Required when using 'soft-token' method.
  mfa_token: Optional[str] = None
  # If set, expects chromedriver to be available in PATH.
  use_chromedriver_on_path = False
  # Only used when `use_chromedriver_on_path` is False. If so, this specifies
  # the directory where the latest version of chromedriver will be downloaded.
  chromedriver_download_path = os.getcwd()

  def __init__(self) -> None:
    """Initialize an options object. Options are the defaults."""
    pass

  @classmethod
  def fromArgsAndEnv(cls, args: argparse.Namespace) -> 'ScraperOptions':
    """Initializes an options object from the given commandline
    arguments and environment variables.

    Args:
      args: The parsed arguments from the commandline from which to construct
      these options.

    Env:
      Reads environment variables.
    """
    types = args.types
    if types.lower() not in ['all', 'accounts', 'transactions']:
      raise ScraperError("Type %s is not valid." % (types))

    options = ScraperOptions()
    options.show_browser = args.debug
    options.scrape_transactions = (
        types.lower() == 'all' or types.lower() == 'transactions')
    options.scrape_accounts = (
        types.lower() == 'all' or types.lower() == 'accounts')

    options.session_path = os.getenv(
        'CHROME_SESSION_PATH', options.session_path)
    options.mfa_method = 'soft-token' if os.getenv('MFA_TOKEN') else 'str'
    options.mfa_token = os.getenv('MFA_TOKEN', options.mfa_token)
    options.use_chromedriver_on_path = os.getenv(
        'USE_CHROMEDRIVER_ON_PATH',
        default='False').lower() in ['true', 't', '1', 'y', 'yes']
    options.chromedriver_download_path = os.getenv(
        'CHROMEDRIVER_PATH', options.chromedriver_download_path)

    return options


def _fetchCookies(cookies_file: str) -> List[str]:
  """Fetches the cookies for Mint if available.

  Args:
    cookies_file: The location of the cookies.

  Returns:
    The fetched cookies, if any.
  """
  cookies: List[str] = []
  if os.path.exists(cookies_file):
    with open(cookies_file, 'rb') as f:
      cookies = pickle.load(f)
  return cookies


def _dumpCookies(mint: mintapi.Mint, cookies_file: str) -> None:
  """Dumps the cookies in the current session to the cookies file.

  Args:
    mint: The current mint session, already logged in.
    cookies_file: The location of the cookies file.
  """
  with open(cookies_file, 'wb') as f:
    pickle.dump(mint.driver.get_cookies(), f)


def _LogIntoMint(creds: Credentials, options: ScraperOptions,
                 cookies: List[str]) -> mintapi.Mint:
  """Logs into mint and retrieves an active connection.

  Args:
    creds: The credentials for the account to log into.
    options: Options for how to connect.
    cookies: Cookies to attach to the session, when provided.

  Returns:
    The mint connection object.
  """
  mint = mintapi.Mint(
      creds.email,
      creds.mintPassword,
      chromedriver_download_path=options.chromedriver_download_path,
      use_chromedriver_on_path=options.use_chromedriver_on_path,
      headless=not options.show_browser,
      imap_account=creds.email,
      imap_folder='Inbox',
      imap_password=creds.emailPassword,
      imap_server=_GLOBAL_CONFIG.IMAP_SERVER,
      mfa_input_callback=None,
      mfa_method=options.mfa_method,
      mfa_token=options.mfa_token,
      session_path=options.session_path,
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
  def getAccountType(originalType: str) -> str:
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

  accounts: List[Dict[str, Any]] = mint.get_account_data()
  return pd.DataFrame([{
      'Name': account['name'],
      'Type': getAccountType(account['name']),
      'Balance': account['value']
  } for account in accounts if account['isActive']])


def _RetrieveTransactions(
        mint: mintapi.Mint, sheet: pygsheets.Spreadsheet) -> pd.DataFrame:
  """Retrieves all Mint transactions using the given credentials.

  The functions also cleans and prepares the transactions to match
  the format expected by Google sheets.

  Args:
    mint: The mint connection object to the active session.

  Returns:
    A data frame of all mint transactions
  """
  all_txns_ws: pygsheets.Worksheet = sheet.worksheet_by_title(
      title=_GLOBAL_CONFIG.RAW_TRANSACTIONS_TITLE)
  old_txns: pd.DataFrame = all_txns_ws.get_as_df()
  cutoff: str = old_txns.Date[
      old_txns.Date.size - _GLOBAL_CONFIG.NUM_TXN_FOR_CUTOFF]
  start_date: str = datetime.strptime(cutoff, "%Y-%m-%d").strftime("%m/%d/%y")

  txns = pd.json_normalize(
      mint.get_transaction_data(limit=20000, remove_pending=False,
                                include_investment=False,
                                start_date=start_date))
  # Only keep txns from cutoff even if more returned by API.
  txns = txns[txns.date >= cutoff]
  spend_txns = txns[
      (~txns['accountRef.name'].isin(
          _GLOBAL_CONFIG.SKIPPED_ACCOUNTS
      )) & txns.isExpense]

  spend_txns = spend_txns[_GLOBAL_CONFIG.COLUMNS]
  spend_txns.columns = _GLOBAL_CONFIG.COLUMN_NAMES
  # Filters that only apply to new txns.
  spend_txns = spend_txns[~(
      spend_txns.ID.map(lambda x: int(x.split('_')[1])).isin(
          _GLOBAL_CONFIG.V1_IGNORED_TXNS)
  )]
  spend_txns = spend_txns.sort_values('Date', ascending=True)

  # Attach old txns.
  spend_txns = pd.concat([old_txns[old_txns.Date < cutoff], spend_txns])

  # Clean-up txns -- this enables us to retroactively clean-up old txns.
  spend_txns.Category = spend_txns.Category.map(_Normalize)
  spend_txns.Merchant = spend_txns.Merchant.map(_NormalizeMerchant)
  spend_txns.Account = spend_txns.Account.map(_Normalize)

  spend_txns = spend_txns[~(
      spend_txns.Category.isin(
          _GLOBAL_CONFIG.IGNORED_CATEGORIES
      ) | spend_txns.Merchant.isin([
          _NormalizeMerchant(merchant)
          for merchant in _GLOBAL_CONFIG.IGNORED_MERCHANTS]
      ) | spend_txns.ID.isin(_GLOBAL_CONFIG.IGNORED_TXNS)
  )]
  return spend_txns


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


def scrape_and_push(
        options: ScraperOptions,
        creds: Credentials,
        cookies: List[str]
) -> mintapi.Mint:
  """Scrapes mint and pushes results.

  Args:
    options: Scraper options to use for this run.
    creds: Credentials for logging into Mint and Google Sheets.
    cookies: Cookies to load, if any.

  Returns:
    Mint session.
  """
  print("Logging into mint")
  mint: mintapi.Mint = _LogIntoMint(creds, options, cookies)
  print("Connecting to sheets.")

  client = pygsheets.authorize(custom_credentials=creds.sheets)
  sheet = client.open(_GLOBAL_CONFIG.WORKSHEET_TITLE)

  def messageWrapper(msg: str, f: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    print(msg)
    sys.stdout.flush()
    return f()

  latestAccounts: pd.DataFrame = (messageWrapper(
      "Retrieving accounts...", lambda: _RetrieveAccounts(mint))
      if options.scrape_accounts else None)
  latestTransactions: pd.DataFrame = (messageWrapper(
      "Retrieving transactions...", lambda: _RetrieveTransactions(mint, sheet))
      if options.scrape_transactions else None)

  print("Retrieval complete. Uploading to sheets...")
  _UpdateGoogleSheet(sheet=sheet,
                     transactions=latestTransactions,
                     accounts=latestAccounts)

  print("Sheets update complate!")

  return mint


def main() -> None:
  """Main function for the script."""
  parser: argparse.ArgumentParser = _ConstructArgumentParser()
  args: argparse.Namespace = parser.parse_args()
  options = ScraperOptions.fromArgsAndEnv(args)
  creds: Credentials = _GetCredentials()

  cookies: List[str] = []
  if args.cookies_path:
    cookies_file = os.path.join(
        options.chromedriver_download_path, args.cookies_path)
    cookies = _fetchCookies(cookies_file)

  mint: mintapi.Mint = scrape_and_push(options, creds, cookies)

  if args.cookies_path:
    _dumpCookies(mint, cookies_file)


if __name__ == '__main__':
  main()

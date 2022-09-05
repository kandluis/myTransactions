import auth
import argparse
import config
import mintapi  # type: ignore
import os
import pandas as pd  # type: ignore
import pickle
import pygsheets  # type: ignore
import remote
import sys
import utils

from typing import Callable, Iterable, List


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


def scrape_and_push(
        options: utils.ScraperOptions,
        creds: auth.Credentials,
        cookies: Iterable[str]
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
  mint: mintapi.Mint = remote.LogIntoMint(creds, options, cookies)
  print("Connecting to sheets.")

  client = pygsheets.authorize(custom_credentials=creds.sheets)
  sheet = client.open(config.GLOBAL.WORKSHEET_TITLE)

  def messageWrapper(msg: str, f: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    print(msg)
    sys.stdout.flush()
    return f()

  latestAccounts: pd.DataFrame = (messageWrapper(
      "Retrieving accounts...", lambda: remote.RetrieveAccounts(mint))
      if options.scrape_accounts else None)
  latestTransactions: pd.DataFrame = (messageWrapper(
      "Retrieving transactions...",
      lambda: remote.RetrieveTransactions(mint, sheet))
      if options.scrape_transactions else None)

  print("Retrieval complete. Uploading to sheets...")
  remote.UpdateGoogleSheet(sheet=sheet,
                           transactions=latestTransactions,
                           accounts=latestAccounts)

  print("Sheets update complate!")

  return mint


def main() -> None:
  """Main function for the script."""
  parser: argparse.ArgumentParser = _ConstructArgumentParser()
  args: argparse.Namespace = parser.parse_args()
  options = utils.ScraperOptions.fromArgsAndEnv(args)
  creds: auth.Credentials = auth.GetCredentials()

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

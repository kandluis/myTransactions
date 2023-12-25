import auth
import argparse
import config
import empower
import pandas as pd  # type: ignore
import pygsheets  # type: ignore
import remote
import sys
import utils

from typing import Callable, Optional


def scrape_and_push(
    options: utils.ScraperOptions, creds: auth.Credentials
) -> empower.PersonalCapital:
    """Scrapes Personal Capital and pushes results.

    Args:
      options: Scraper options to use for this run.
      creds: Credentials for logging into Personal Capital and Google Sheets.
      cookies: Cookies to load, if any.

    Returns:
      Personal Capital session.
    """
    print("Logging in...")
    connection: empower.PersonalCapital = remote.Authenticate(creds, options)
    print("Connecting to sheets.")
    client = pygsheets.authorize(custom_credentials=creds.sheets)
    sheet = client.open(config.GLOBAL.WORKSHEET_TITLE)

    def messageWrapper(msg: str, f: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        print(msg)
        sys.stdout.flush()
        return f()

    latestAccounts: Optional[pd.DataFrame] = (
        messageWrapper(
            "Retrieving accounts...", lambda: remote.RetrieveAccounts(connection)
        )
        if options.scrape_accounts
        else None
    )
    latestTransactions: Optional[pd.DataFrame] = (
        messageWrapper(
            "Retrieving transactions...",
            lambda: remote.RetrieveTransactions(connection, sheet),
        )
        if options.scrape_transactions
        else None
    )

    print("Retrieval complete. Uploading to sheets...")
    if not options.dry_run:
        remote.UpdateGoogleSheet(
            sheet=sheet, transactions=latestTransactions, accounts=latestAccounts
        )
        print("Sheets update complate!")
    else:
        print("Dry run successful")

    return connection


def main() -> None:
    """Main function for the script."""
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args: argparse.Namespace = parser.parse_args()
    options = utils.ScraperOptions.fromArgsAndEnv(args)
    creds: auth.Credentials = auth.GetCredentials()

    _ = scrape_and_push(options, creds)


if __name__ == "__main__":
    main()

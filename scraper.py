import auth
import argparse
import config
import empower
import pandas as pd
import pygsheets
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

    print(f"Retrieval complete.{'' if options.dry_run else 'Uploading to sheets...'}")
    if not options.dry_run:
        remote.UpdateGoogleSheet(
            sheet=sheet, transactions=latestTransactions, accounts=latestAccounts
        )
        print("Sheets update complate!")
    if latestAccounts is not None and options.debug:
        latestAccounts.to_csv("accounts.csv")
    if latestTransactions is not None and options.debug:
        latestTransactions.to_csv("transactions.csv")

    return connection


def main(argv=None) -> None:
    """Main function for the script."""
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args: argparse.Namespace = parser.parse_args(argv)
    options = utils.ScraperOptions.fromArgsAndEnv(args)
    creds: auth.Credentials = auth.GetCredentials()

    _ = scrape_and_push(options, creds)


if __name__ == "__main__":
    main()

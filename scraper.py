import argparse
import auth
import config
import empower
import fcntl
import logging
import os
import pandas as pd
import pygsheets
import remote
import sys
import utils

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_SCRAPE_LOCK_FILE = Path(os.getenv("SCRAPE_LOCK_FILE", "/tmp/scraper.lock"))


@contextmanager
def acquire_scrape_lock(lock_path: Path = DEFAULT_SCRAPE_LOCK_FILE):
    """Acquire a non-blocking cross-process lock for the scraper."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise utils.ScraperError("scrape already running") from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def scrape_lock_available(lock_path: Path = DEFAULT_SCRAPE_LOCK_FILE) -> bool:
    """Return whether the scraper lock can be acquired right now."""
    try:
        with acquire_scrape_lock(lock_path):
            return True
    except utils.ScraperError:
        return False


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
    with acquire_scrape_lock():
        logger.info("Logging in...")
        connection: empower.PersonalCapital = remote.Authenticate(creds, options)
        logger.info("Connecting to sheets.")
        client = pygsheets.authorize(custom_credentials=creds.sheets)
        sheet = client.open(config.GLOBAL.WORKSHEET_TITLE)

        def messageWrapper(msg: str, f: Callable[[], pd.DataFrame]) -> pd.DataFrame:
            logger.info(msg)
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

        logger.info(
            f"Retrieval complete.{'' if options.dry_run else ' Uploading to sheets...'}"
        )
        if not options.dry_run:
            remote.UpdateGoogleSheet(
                sheet=sheet, transactions=latestTransactions, accounts=latestAccounts
            )
            logger.info("Sheets update complate!")
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

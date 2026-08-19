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
import plaid_source
import sys
import utils

from contextlib import contextmanager
from datetime import datetime, timezone
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


def _open_sheet(sheets_credentials: object) -> pygsheets.Spreadsheet:
    client = pygsheets.authorize(custom_credentials=sheets_credentials)
    return client.open(config.GLOBAL.WORKSHEET_TITLE)


def scrape_plaid_and_push(options: utils.ScraperOptions) -> None:
    """Run the configured Plaid cursor sync without requiring Empower secrets."""
    with acquire_scrape_lock():
        sheet = _open_sheet(auth.GetGoogleCredentials())
        store = plaid_source.SheetStateStore(sheet)
        state = store.load()
        items = state.get("items", {})
        active = [
            (item_id, item)
            for item_id, item in items.items()
            if item.get("status") == "active"
        ]
        if not active:
            raise plaid_source.PlaidError(
                "no_connected_items", "No approved Plaid accounts are connected"
            )
        client = plaid_source.PlaidClient()
        tx_ws = sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
        existing = tx_ws.get_as_df(numerize=False)
        existing = existing.reindex(columns=config.GLOBAL.COLUMN_NAMES, fill_value="")
        all_added: list[pd.DataFrame] = []
        modified_ids: set[str] = set()
        removed_ids: set[str] = set()
        accounts: list[dict[str, object]] = []
        item_errors: list[plaid_source.PlaidError] = []
        for item_id, item in active:
            try:
                added, modified, removed, cursor = client.sync(
                    str(item["access_token"]), str(item.get("cursor", ""))
                )
            except plaid_source.PlaidError as exc:
                item["last_error"] = exc.code
                item["last_sync_at"] = datetime.now(timezone.utc).isoformat()
                items[item_id] = item
                item_errors.append(exc)
                continue
            all_added.extend(
                [
                    plaid_source.transaction_frame(added, item),
                    plaid_source.transaction_frame(modified, item),
                ]
            )
            modified_ids.update(
                "plaid:" + str(t.get("transaction_id", "")) for t in modified
            )
            removed_ids.update(
                "plaid:" + str(t.get("transaction_id", "")) for t in removed
            )
            for account in client.accounts(str(item["access_token"])):
                if (
                    item.get("selected_account_ids")
                    and account.get("account_id") not in item["selected_account_ids"]
                ):
                    continue
                accounts.append(
                    {
                        "Name": plaid_source._account_name(account, item),
                        "Type": account.get("type", "Unknown"),
                        "Balance": account.get("balances", {}).get("current"),
                        "inferredType": account.get("subtype", ""),
                    }
                )
            item["cursor"] = cursor
            item["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            item["last_error"] = ""
            items[item_id] = item
        if len(item_errors) == len(active):
            store.save(state)
            raise item_errors[0]
        additions = (
            pd.concat(all_added, ignore_index=True)
            if all_added
            else pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES)
        )
        merged = plaid_source.merge_transactions(
            existing, additions, modified_ids, removed_ids
        )
        if not options.dry_run:
            remote.UpdateGoogleSheet(
                sheet,
                merged if options.scrape_transactions else None,
                pd.DataFrame(accounts) if options.scrape_accounts else None,
            )
            store.save(state)


def scrape_and_push(
    options: utils.ScraperOptions, creds: Optional[auth.Credentials] = None
) -> Optional[empower.PersonalCapital]:
    """Scrapes Personal Capital and pushes results.

    Args:
      options: Scraper options to use for this run.
      creds: Credentials for logging into Personal Capital and Google Sheets.

    Returns:
      Personal Capital session.
    """
    if plaid_source.is_configured():
        scrape_plaid_and_push(options)
        return None

    if creds is None:
        creds = auth.GetCredentials()
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

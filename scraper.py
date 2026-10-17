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
import time
import utils

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_SCRAPE_LOCK_FILE = Path(os.getenv("SCRAPE_LOCK_FILE", "/tmp/scraper.lock"))
DURABLE_STATUS_MAX_ATTEMPTS = 3
DURABLE_STATUS_RETRY_DELAYS = (1, 2)


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _claim_durable_scrape_job() -> Optional[str]:
    """Mark a queued manual job running on the one-shot scraper Machine."""
    try:
        sheet = _open_sheet(auth.GetGoogleCredentials())
        store = plaid_source.SheetStateStore(sheet)
        state = store.load()
        job = state.get("scrape_job")
        if not isinstance(job, dict) or job.get("state") != "queued":
            return None
        job["state"] = "running"
        job["started_at"] = _utc_now()
        job["error"] = ""
        job["error_code"] = ""
        state["scrape_job"] = job
        store.save(state)
        return str(job.get("job_id", "")) or None
    except Exception:
        logger.exception("Could not claim the durable manual scrape job")
        return None


def _finish_durable_scrape_job(
    job_id: Optional[str], *, error: Optional[Exception] = None
) -> None:
    """Persist the terminal worker result so web restarts do not lose status."""
    if not job_id:
        return
    for attempt in range(DURABLE_STATUS_MAX_ATTEMPTS):
        try:
            # Reload the state for every retry so an intermittent Sheets failure
            # never writes a stale version over a concurrently updated job.
            sheet = _open_sheet(auth.GetGoogleCredentials())
            store = plaid_source.SheetStateStore(sheet)
            state = store.load()
            job = state.get("scrape_job")
            if not isinstance(job, dict) or str(job.get("job_id", "")) != job_id:
                return
            job["finished_at"] = _utc_now()
            if error is None:
                job["state"] = "succeeded"
                job["last_successful_at"] = job["finished_at"]
                job["error"] = ""
                job["error_code"] = ""
            else:
                job["state"] = "failed"
                job["error"] = str(error)
                job["error_code"] = (
                    error.code
                    if isinstance(error, plaid_source.PlaidError)
                    else "sync_failed"
                )
            state["scrape_job"] = job
            store.save(state)
            return
        except Exception:
            if attempt == DURABLE_STATUS_MAX_ATTEMPTS - 1:
                raise
            delay = DURABLE_STATUS_RETRY_DELAYS[attempt]
            logger.warning(
                "Could not persist durable manual scrape result (attempt %d/%d); "
                "retrying in %s seconds",
                attempt + 1,
                DURABLE_STATUS_MAX_ATTEMPTS,
                delay,
                exc_info=True,
            )
            time.sleep(delay)


def _sync_item_transactions(
    client: plaid_source.PlaidClient,
    item: dict[str, Any],
    all_added: list[pd.DataFrame],
    modified_ids: set[str],
    removed_ids: set[str],
) -> Optional[plaid_source.PlaidError]:
    """Synchronize one item and update its cursor only on success."""
    try:
        added, modified, removed, cursor = client.sync(
            str(item["access_token"]), str(item.get("cursor", ""))
        )
        added_frame = plaid_source.transaction_frame(added, item)
        modified_frame = plaid_source.transaction_frame(modified, item)
        all_added.extend([added_frame, modified_frame])
        modified_ids.update(
            "plaid:" + str(transaction.get("transaction_id", ""))
            for transaction in modified
        )
        removed_ids.update(
            "plaid:" + str(transaction.get("transaction_id", ""))
            for transaction in removed
        )
        prior_imported_ids = {
            str(transaction_id)
            for transaction_id in item.get("imported_transaction_ids", [])
        }
        item["imported_transaction_ids"] = sorted(
            (
                prior_imported_ids
                | set(added_frame["ID"].astype(str))
                | set(modified_frame["ID"].astype(str))
            )
            - {
                "plaid:" + str(transaction.get("transaction_id", ""))
                for transaction in removed
            }
        )
        item["cursor"] = cursor
        return None
    except plaid_source.PlaidError as exc:
        return exc


def _collect_item_accounts(
    client: plaid_source.PlaidClient,
    item: dict[str, Any],
    accounts: list[dict[str, object]],
) -> Optional[plaid_source.PlaidError]:
    """Collect one item's account snapshot without affecting its cursor."""
    try:
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
        return None
    except plaid_source.PlaidError as exc:
        return exc


def _raise_plaid_item_errors(
    errors: list[plaid_source.PlaidError], has_successful_work: bool
) -> None:
    """Surface incomplete synchronization after successful data is committed."""
    if not errors:
        return
    if not has_successful_work:
        raise errors[0]
    failed_codes = ", ".join(sorted({error.code for error in errors}))
    raise plaid_source.PlaidError(
        "partial_sync_failed",
        f"One or more Plaid items could not be synchronized: {failed_codes}",
    )


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
        existing = pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES)
        if options.scrape_transactions:
            tx_ws = sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
            existing = tx_ws.get_as_df(numerize=False)
            existing = existing.reindex(
                columns=config.GLOBAL.COLUMN_NAMES, fill_value=""
            )
        all_added: list[pd.DataFrame] = []
        modified_ids: set[str] = set()
        removed_ids: set[str] = set()
        accounts: list[dict[str, object]] = []
        item_errors: list[plaid_source.PlaidError] = []
        successful_transactions = False
        successful_accounts = False
        accounts_complete = options.scrape_accounts
        for item_id, item in active:
            item_error: Optional[plaid_source.PlaidError] = None
            if options.scrape_transactions:
                item_error = _sync_item_transactions(
                    client, item, all_added, modified_ids, removed_ids
                )
                if item_error is None:
                    successful_transactions = True
                else:
                    item_errors.append(item_error)
            if options.scrape_accounts:
                account_error = _collect_item_accounts(client, item, accounts)
                if account_error is None:
                    successful_accounts = True
                else:
                    item_error = account_error
                    item_errors.append(account_error)
                    accounts_complete = False
            item["last_sync_at"] = datetime.now(timezone.utc).isoformat()
            item["last_error"] = item_error.code if item_error else ""
            items[item_id] = item
        additions = (
            pd.concat(all_added, ignore_index=True)
            if all_added
            else pd.DataFrame(columns=config.GLOBAL.COLUMN_NAMES)
        )
        merged = plaid_source.merge_transactions(
            existing, additions, modified_ids, removed_ids
        )
        has_successful_work = successful_transactions or successful_accounts
        has_sheet_work = successful_transactions or (
            successful_accounts and accounts_complete
        )
        if not options.dry_run and has_sheet_work:
            remote.UpdateGoogleSheet(
                sheet,
                merged if successful_transactions else None,
                (
                    pd.DataFrame(accounts)
                    if options.scrape_accounts and accounts_complete
                    else None
                ),
                mark_scrape_success=(options.scrape_transactions and not item_errors),
            )
            store.save(state)
        elif not options.dry_run and item_errors:
            store.save(state)
        _raise_plaid_item_errors(item_errors, has_successful_work)


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
    creds: Optional[auth.Credentials] = (
        None if plaid_source.is_configured() else auth.GetCredentials()
    )

    durable_job_id = None if options.dry_run else _claim_durable_scrape_job()
    try:
        _ = scrape_and_push(options, creds)
    except Exception as exc:
        if durable_job_id:
            try:
                _finish_durable_scrape_job(durable_job_id, error=exc)
            except Exception:
                logger.exception(
                    "Could not persist durable failure status after scrape error"
                )
        raise
    if durable_job_id:
        _finish_durable_scrape_job(durable_job_id)


if __name__ == "__main__":
    main()

import auth
import utils
import config
import empower
import mintapi  # type: ignore
import pandas as pd  # type: ignore
import pygsheets  # type: ignore
import socket
import time

from datetime import datetime

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
)


def _Normalize(value: str) -> str:
    """Normalizes the str value

    Args:
      value: The str to be normalized.

    Returns:
      The normalized str.
    """
    return "".join(ch for ch in value if ch.isalnum() or ch.isspace()).title()


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
        if nChars >= config.GLOBAL.MAX_MERCHANT_NAME_CHARS:
            break
    normalized = " ".join("".join(trimmed).split()).title()
    for simpleName in config.GLOBAL.MERCHANT_NORMALIZATION:
        if simpleName in normalized:
            return simpleName
    return normalized


def LogIntoPC(
    creds: auth.Credentials, options: utils.ScraperOptions
) -> empower.PersonalCapital:
    """Logs into Personal Capital and retrieves an active API connection.

    Args:
      creds: The credentials for the account to log into.
      options: Options for how to connect.

    Returns:
      The PersonalCapital connection object.
    """
    pc = empower.PersonalCapital()
    pc.login(
        email=creds.username,
        password=creds.password,
        mfa_method=options.mfa_method,
        mfa_token=options.mfa_token,
    )
    return pc


def LogIntoMint(
    creds: auth.Credentials, options: utils.ScraperOptions, cookies: Iterable[str]
) -> mintapi.Mint:
    """Logs into mint and retrieves an active connection.

    Args:
      creds: The credentials for the account to log into.
      options: Options for how to connect.
      cookies: Cookies to attach to the session, when provided.

    Returns:
      The mint connection object.
    """
    mint = mintapi.Mint(
        creds.username,
        creds.password,
        chromedriver_download_path=options.chromedriver_download_path,
        use_chromedriver_on_path=options.use_chromedriver_on_path,
        headless=not options.show_browser,
        imap_account=creds.username,
        imap_folder="Inbox",
        imap_password=creds.emailPassword,
        imap_server=config.GLOBAL.IMAP_SERVER,
        mfa_input_callback=None,
        mfa_method=options.mfa_method,
        mfa_token=options.mfa_token,
        session_path=options.session_path,
        wait_for_sync=config.GLOBAL.WAIT_FOR_ACCOUNT_SYNC,
    )
    time.sleep(5)

    # Load cookies if provided. These are cookies only for mint.com domain.
    [mint.driver.add_cookie(cookie) for cookie in cookies]
    return mint


def RetrieveAccounts(mint: mintapi.Mint) -> pd.DataFrame:
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
            config.GLOBAL.ACCOUNT_NAME_TO_TYPE_MAP,
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            if substring.lower() in originalType.lower():
                return accountType
        print("No account type for account with type: %s" % originalType)
        return "Unknown - %s" % (originalType)

    accounts: List[Dict[str, Any]] = mint.get_account_data()
    return pd.DataFrame(
        [
            {
                "Name": account["name"],
                "Type": getAccountType(account["name"]),
                "Balance": account["value"],
            }
            for account in accounts
            if account["isActive"]
        ]
    )


def RetrieveTransactions(
    mint: mintapi.Mint, sheet: pygsheets.Spreadsheet
) -> pd.DataFrame:
    """Retrieves all Mint transactions using the given credentials.

    The functions also cleans and prepares the transactions to match
    the format expected by Google sheets.

    Args:
      mint: The mint connection object to the active session.

    Returns:
      A data frame of all mint transactions
    """
    all_txns_ws: pygsheets.Worksheet = sheet.worksheet_by_title(
        title=config.GLOBAL.RAW_TRANSACTIONS_TITLE
    )
    old_txns: pd.DataFrame = all_txns_ws.get_as_df()
    cutoff: str = old_txns.Date[old_txns.Date.size - config.GLOBAL.NUM_TXN_FOR_CUTOFF]
    start_date: str = datetime.strptime(cutoff, "%Y-%m-%d").strftime("%m/%d/%y")

    txns = pd.json_normalize(
        mint.get_transaction_data(
            limit=20000,
            remove_pending=True,
            include_investment=False,
            start_date=start_date,
        )
    )
    # Only keep txns from cutoff even if more returned by API.
    txns = txns[txns.date >= cutoff]
    spend_txns = txns[
        (~txns["accountRef.name"].isin(config.GLOBAL.SKIPPED_ACCOUNTS)) & txns.isExpense
    ]

    spend_txns = spend_txns[config.GLOBAL.COLUMNS]
    spend_txns.columns = config.GLOBAL.COLUMN_NAMES
    # Filters that only apply to new txns.
    spend_txns = spend_txns[
        ~(
            spend_txns.ID.map(lambda x: int(x.split("_")[1])).isin(
                config.GLOBAL.V1_IGNORED_TXNS
            )
        )
    ]
    spend_txns = spend_txns.sort_values("Date", ascending=True)

    # Attach old txns.
    spend_txns = pd.concat([old_txns[old_txns.Date < cutoff], spend_txns])

    # Clean-up txns -- this enables us to retroactively clean-up old txns.
    spend_txns.Category = spend_txns.Category.map(_Normalize)
    spend_txns.Merchant = spend_txns.Merchant.map(_NormalizeMerchant)
    spend_txns.Account = spend_txns.Account.map(_Normalize)
    spend_txns.Description = spend_txns.Description.map(_Normalize)

    ignored_category = spend_txns.Category.isin(config.GLOBAL.IGNORED_CATEGORIES)
    ignored_merchant = spend_txns.Merchant.isin(
        [_NormalizeMerchant(merchant) for merchant in config.GLOBAL.IGNORED_MERCHANTS]
    )
    ignored_txn = spend_txns.ID.isin(config.GLOBAL.IGNORED_TXNS)
    spend_txns = spend_txns[~(ignored_category | ignored_merchant | ignored_txn)]
    deduped_txns = spend_txns.drop_duplicates(
        subset=config.GLOBAL.IDENTIFIER_COLUMNS, ignore_index=True
    )
    return deduped_txns


def UpdateGoogleSheet(
    sheet: pygsheets.Spreadsheet,
    transactions: Optional[pd.DataFrame],
    accounts: Optional[pd.DataFrame],
) -> None:
    """Updates the given transactions sheet with the transactions data

    Args:
      sheet: The sheet containing our transaction analysis and visualization.
      data: The new, cleaned, raw transaction data to analyze.
    """
    if transactions is not None:
        all_transactions_ws = sheet.worksheet_by_title(
            title=config.GLOBAL.RAW_TRANSACTIONS_TITLE
        )
        all_transactions_ws.set_dataframe(transactions, "A1", fit=True)

    if accounts is not None:
        all_accounts_ws = sheet.worksheet_by_title(
            title=config.GLOBAL.RAW_ACCOUNTS_TITLE
        )
        all_accounts_ws.set_dataframe(accounts, "A1", fit=True)

    settings_ws = sheet.worksheet_by_title(title=config.GLOBAL.SETTINGS_SHEET_TITLE)
    # Update with current time.
    today = datetime.today()
    today_string = today.strftime("%d-%B-%Y %H:%M:%S %Z")
    hostname = socket.gethostname()
    settings_ws.set_dataframe(pd.DataFrame([today_string, hostname]), "D2")

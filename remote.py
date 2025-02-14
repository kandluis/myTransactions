import auth
import utils
import config
import empower
import pandas as pd
import pygsheets
import socket

from datetime import datetime, timezone, timedelta
from datetime import date

from typing import (
    Any,
    cast,
    Optional,
)


def _trim(merchant: str) -> str:
    trimmed = []
    for ch in merchant:
        if ch.isalpha() or ch.isspace():
            trimmed.append(ch)
    return " ".join("".join(trimmed).replace("xx", "").split()).title()


def _normalize(merchant: str) -> str:
    merchant = merchant.lower()
    for prefix in config.GLOBAL.STARTS_WITH_REMOVAL:
        if merchant.startswith(prefix.lower()):
            merchant = merchant[len(prefix):]
    if merchant.startswith("amzn mktp "):
        merchant = f"Amazon {merchant[10:]}"
    for suffix in config.GLOBAL.ENDS_WITH_REMOVAL:
        if merchant.endswith(suffix.lower()):
            merchant = merchant[: len(merchant) - len(suffix)]
    for src, dst in config.GLOBAL.MERCHANT_NORMALIZATION_PAIRS:
        merchant = merchant.replace(src.lower(), dst.lower())
    normalized = _trim(merchant)
    for simpleName in config.GLOBAL.MERCHANT_NORMALIZATION:
        if simpleName.lower() in normalized.lower():
            return simpleName
    return normalized


def _Normalize(value: str) -> str:
    """Normalizes the str value

    Args:
      value: The str to be normalized.

    Returns:
      The normalized str.
    """
    return " ".join(
        "".join(
            ch for ch in value if ch.isalnum() or ch.isspace() or ch in ("/")
        ).split()
    ).title()


def _NormalizeMerchant(merchant: str) -> str:
    """Normalizes the str merchant of a merchant.

    Args:
      merchant: The str to be normalized.

    Returns:
      The normalized merchant.
    """
    # Keep normalizing until stable or if we'll end up empty.
    maxGoes = 30
    while maxGoes > 0:
        norm = _normalize(merchant)
        maxGoes = 0 if norm == merchant or len(norm) == 0 else maxGoes - 1
        merchant = norm
        if maxGoes > 0 and maxGoes < 5:
            print(f"Might enter a cycle with {merchant}")
    return merchant


def _cleanTxns(txns: pd.DataFrame) -> pd.DataFrame:
    """Cleans the txns given.

    Args:
        txns: The txns to clean. A copy is made.

    Returns:
        The cleaned txns with normalized data.
    """
    cleaned = txns[:]
    cleaned.Category = cleaned.Category.map(_Normalize)
    cleaned.Merchant = cleaned.Merchant.map(_NormalizeMerchant)
    cleaned.Account = cleaned.Account.map(_Normalize)
    cleaned.Description = cleaned.Description.map(_Normalize)

    ignored_category = cleaned.Category.isin(
        [_Normalize(category) for category in config.GLOBAL.IGNORED_CATEGORIES]
    )
    ignored_merchant = cleaned.Merchant.isin(
        [_NormalizeMerchant(merchant) for merchant in config.GLOBAL.IGNORED_MERCHANTS]
    )
    ignored_txn = cleaned.ID.isin(config.GLOBAL.IGNORED_TXNS)
    ignored_account = cleaned.Account.isin(
        [_Normalize(account) for account in config.GLOBAL.SKIPPED_ACCOUNTS]
    )
    cleaned = cleaned[
        ~(ignored_category | ignored_merchant | ignored_txn | ignored_account)
    ]
    return cleaned


def Authenticate(
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


def RetrieveAccounts(conn: empower.PersonalCapital) -> pd.DataFrame:
    """Retrieves the latest account information.

    Args:
      conn: The account from which to retrieve account info.

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

    accounts = conn.get_account_data()["accounts"]
    return pd.DataFrame(
        [
            {
                "Name": account["name"],
                "Type": getAccountType(account["name"]),
                "Balance": account["balance"],
                "inferredType": account["accountType"],
            }
            for account in accounts
            if not account["closedDate"] and account.get("name") is not None
        ]
    )


def RetrieveTransactions(
    conn: empower.PersonalCapital, sheet: pygsheets.Spreadsheet
) -> pd.DataFrame:
    """Retrieves all transactions using the given credentials.

    The functions also cleans and prepares the transactions to match
    the format expected by Google sheets.

    Args:
      conn: The connection object to the active session.
      sheet: The sheet object from which to fetch old txns.

    Returns:
      A data frame of all transactions.
    """
    all_txns_ws: pygsheets.Worksheet = sheet.worksheet_by_title(
        title=config.GLOBAL.RAW_TRANSACTIONS_TITLE
    )
    old_txns: pd.DataFrame = all_txns_ws.get_as_df(numerize=False)
    old_txns = old_txns[config.GLOBAL.COLUMN_NAMES]
    cutoff: Optional[date] = (
        max(
            datetime.strptime(
                old_txns.Date[
                    max(0, old_txns.Date.size - config.GLOBAL.NUM_TXN_FOR_CUTOFF)
                ],
                "%Y-%m-%d",
            ).date(),
            datetime.strptime(config.GLOBAL.PC_MIGRATION_DATE, "%Y-%m-%d").date(),
        )
        if config.GLOBAL.NUM_TXN_FOR_CUTOFF > 0
        else None
    )
    resp = conn.get_transaction_data(
        start_date=cutoff,
    )
    txns = pd.json_normalize(
        cast(
            list[dict[str, Any]],
            resp["transactions"],
        )
    )
    # Only keep txns from cutoff even if more returned by API.
    txns = txns[txns.transactionDate >= cutoff.strftime("%Y-%m-%d")] if cutoff else txns
    # Only spending and non-investment txns.
    spend_txns = txns[
        (txns.isSpending | txns.isCashOut) & txns.investmentType.isna()
    ].copy()
    # Get amounts correct. Credits are positive, everything else is negative.
    spend_txns.amount = spend_txns.amount * spend_txns.isCredit.map(
        lambda isCredit: 1 if isCredit else -1
    )

    spend_txns = spend_txns[config.GLOBAL.COLUMNS]
    spend_txns.columns = pd.Index(config.GLOBAL.COLUMN_NAMES)
    spend_txns = spend_txns.sort_values("Date", ascending=True)

    spend_txns.Merchant = spend_txns.Merchant.fillna(spend_txns.Description)

    old_txns = (
        old_txns[old_txns.Date < cutoff.strftime("%Y-%m-%d")] if cutoff else old_txns
    )
    if config.GLOBAL.CLEAN_UP_OLD_TXNS:
        combined = pd.concat([old_txns, spend_txns])
        combined = _cleanTxns(combined)
    else:
        spend_txns = _cleanTxns(spend_txns)
        combined = pd.concat([old_txns, spend_txns])

    deduped_txns = combined.drop_duplicates(
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
      transactions: The new, cleaned, raw transaction data to analyze.
      accounts: The new, cleaned, raw accounts.
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
    today = datetime.now(tz=timezone(-timedelta(hours=8)))
    today_string = today.strftime("%d-%B-%Y %H:%M:%S %Z")
    hostname = socket.gethostname()
    settings_ws.set_dataframe(pd.DataFrame([today_string, hostname]), "D2")

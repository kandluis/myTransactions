import auth
import utils
import config
import empower
import pandas as pd  # type: ignore
import pygsheets  # type: ignore
import socket

from datetime import datetime

from typing import (
    Any,
    Optional,
)


def _Normalize(value: str) -> str:
    """Normalizes the str value

    Args:
      value: The str to be normalized.

    Returns:
      The normalized str.
    """
    return " ".join(
        "".join(ch for ch in value if ch.isalnum() or ch.isspace()).split()
    ).title()


def _NormalizeMerchant(merchant: str) -> str:
    """Normalizes the str merchant of a merchant.

    Args:
      merchant: The str to be normalized.

    Returns:
      The normalized merchant.
    """
    if merchant.lower().startswith("aplpay") or merchant.lower().startswith("gglpay"):
        merchant = merchant[7:]
    if merchant.lower().startswith("Amzn Mktp "):
        merchant = "Amzn Mktp"
    trimmed = []
    for ch in merchant:
        if ch.isalpha() or ch.isspace():
            trimmed.append(ch)
    normalized = " ".join("".join(trimmed).lower().replace("xx", "").split()).title()
    for simpleName in config.GLOBAL.MERCHANT_NORMALIZATION:
        if simpleName in normalized:
            return simpleName
    return normalized


def _cleanTxns(txns: pd.DataFrame) -> pd.DataFrame:
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

    account_data: dict = conn.get_account_data()
    accounts = account_data["accounts"]
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

    Returns:
      A data frame of all transactions.
    """
    all_txns_ws: pygsheets.Worksheet = sheet.worksheet_by_title(
        title=config.GLOBAL.RAW_TRANSACTIONS_TITLE
    )
    old_txns: pd.DataFrame = all_txns_ws.get_as_df(numerize=False)
    cutoff: str = old_txns.Date[old_txns.Date.size - config.GLOBAL.NUM_TXN_FOR_CUTOFF]
    start_date: datetime.datetime = max(
        datetime.strptime(cutoff, "%Y-%m-%d"),
        datetime.strptime(config.GLOBAL.PC_MIGRATION_DATE, "%Y-%m-%d"),
    )
    txns = pd.json_normalize(
        conn.get_transaction_data(
            start_date=start_date,
        )
    )
    # Only keep txns from cutoff even if more returned by API.
    txns = txns[txns.transactionDate >= cutoff]
    # Only spending and non-investment txns.
    spend_txns = txns[
        (txns.isSpending | txns.isCashOut) & txns.investmentType.isna()
    ].copy()
    # Get amounts correct. Credits are positive, everything else is negative.
    spend_txns.amount = spend_txns.amount * spend_txns.isCredit.map(
        lambda isCredit: 1 if isCredit else -1
    )

    spend_txns = spend_txns[config.GLOBAL.COLUMNS]
    spend_txns.columns = config.GLOBAL.COLUMN_NAMES
    spend_txns = spend_txns.sort_values("Date", ascending=True)

    spend_txns.Merchant = spend_txns.Merchant.fillna(spend_txns.Description)

    if config.GLOBAL.CLEAN_UP_OLD_TXNS:
        combined = pd.concat([old_txns[old_txns.Date < cutoff], spend_txns])
        combined = _cleanTxns(combined)
    else:
        spend_txns = _cleanTxns(spend_txns)
        combined = pd.concat([old_txns[old_txns.Date < cutoff], spend_txns])

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

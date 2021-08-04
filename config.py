from typing import List, Optional, Text


class Config:
  """A class capturing configurable settings for the mint scraper."""

  def __init__(self: 'Config') -> None:
    """Initializes the config to the default values.

    Properties:
      JOINT_SPENDING_ACCOUNTS: The account names which are held jointly.
        Only transactions from accounts matching these are uploaded to
        the Google Sheet.

      COLUMNS: The column names of the retrieved dataframe return by the
        mintapi library.
      COLUMN_NAMES: COLUMN_NAMES[i] is the column name in the Google sheet
        of the corresponding COLUMNs[i]
      RAW_SHEET_TITLE: The name of the sheet which contains the raw
        transactions.
      SETTINGS_SHEET_TITLE: The name of the sheet containing the setting
        page.
      KEYS_FILE: The file path (relative) of the keys to use when using the
        Google Sheets API
      WORKSHEET_TITLE: The title of the worksheet in Google Drive where
        transactions are uploaded.
      IGNORED_MERCHANTS: A list of merchants which are filtered out when
        processing transactions.
      IGNORED_CATEGORIES: A list of categories which are filtered out when
        processing transactions.
      SESSION_PATH: The full path to where Chrome session data can be
        stored and retrieved from.
      IMAP_SERVER: The IMAP server to use for MFA using email.
      WAIT_FOR_ACCOUNT_SYNC: Whether or not to wait for account syncing.
    """

    self.JOINT_SPENDING_ACCOUNTS: List[Text] = [
        'Amazon Card - Luis',
        'Amazon Store Card',
        'Bank of America Travel Rewards Visa Signature',
        'CapitalOne Venture Card',
        'Chase Business Unlimited - Belinda',
        'Chase Business Unlimited - Luis',
        'Citi - Personal',
        'Citi Dividend Miles'
        'Citi Premier Card',
        'CREDIT CARD',
        'Discover',
        'Freedom - Belinda',
        'Freedom Unlimited - Belinda',
        'Freedom',
        'LemonBunny',
        'Marriott Rewards',
        'Platinum Card',
        'Preferred',
        'Southest Business - Belinda',
        'Southwest Business - Luis',
        'Southwest Rapid Rewards',
        'Spark Visa Signature Business',
    ]
    self.COLUMNS: List[Text] = [
        'odate', 'mmerchant', 'amount', 'category', 'account', 'id']
    self.COLUMN_NAMES: List[Text] = [
        'Date', 'Merchant', 'Amount', 'Category', 'Account', 'ID']
    self.ACCOUNT_COLUMN_NAMES: List[Text] = ['Name', 'Type', 'Balance']

    self.RAW_TRANSACTIONS_TITLE: Text = "Raw - All Transactions"
    self.RAW_ACCOUNTS_TITLE = 'Raw - All Accounts'
    self.SETTINGS_SHEET_TITLE: Text = 'Settings'
    self.WORKSHEET_TITLE: Text = "Transactions Worksheet"

    # Paid for Luis' Family's phones are not counted.
    # Ignore SCPD Payments.
    self.IGNORED_MERCHANTS: List[Text] = [
        'Project Fi',
        'Stanford Scpd Ca',
        'Stanford Scpd 6507253016 Ca',
        'Anita Borg Institute',
        'Graves Bail Bonds',
        'Stanford Scpd',
    ]
    # Credit card payments are redundant.
    self.IGNORED_CATEGORIES: List[Text] = [
        'Credit Card Payment',
        'Transfer',
        'Paycheck',
        'Income',
    ]
    # Ignore specific transactions.
    self.IGNORED_TXNS: List[int] = [
        2675570707,
        2461681673,
        2482214183,
        2504269103,
        2510726212,
        2553593280,
        2553593281,
        2556300742,
        2559139111,
        2566235034,
        2573036964,
        2618759691,
        2651591652,
        2683357551,
        2683357555,
        2683357558,
        2688868455,
        2699871142,
        2700599726,
        2701555871,
        2702719675,
        2722631725,
        2728575778,
    ]
    self.IMAP_SERVER: Optional[Text] = "imap.gmail.com"
    self.WAIT_FOR_ACCOUNT_SYNC: bool = False
    # substring to account type string mapping.
    self.ACCOUNT_NAME_TO_TYPE_MAP = [
        ('401(K) SAVINGS PLAN', 'Restricted Stock'),
        ('529 College Plan', 'Restricted Stock'),
        ('Acorns', 'Stock'),
        ('Ally', 'Cash'),
        ('Apple', 'Credit'),
        ('B. ZENG', 'Credit'),
        ('Bank', 'Cash'),
        ('Belinda and Luis', 'Stock'),
        ('Brokerage', 'Stock'),
        ('Build Wealth', 'Stock'),
        ('C2012 RSU 10/05/2016 776.47 63 Class-C', 'Stock'),
        ('Card', 'Credit'),
        ('Cash', 'Cash'),
        ('Chase Business Unlimited - Belinda', 'Credit'),
        ('Chase Business Unlimited - Luis', 'Credit'),
        ('Checking', 'Cash'),
        ('Citi', 'Credit'),
        ('Credit', 'Credit'),
        ('Deferred Comp', 'Restricted Cash'),
        ('Discover', 'Credit'),
        ('Equity Awards', 'Stock'),
        ('ESPP_31003770405', 'Stock'),
        ('FACEBOOK', 'Stock'),
        ('Freedom', 'Credit'),
        ('GSU', 'GOOG'),
        ('Health Savings', 'Restricted Cash'),
        ('HSA Investment', 'Restricted Stock'),
        ('Individual          ', 'Stock'),
        ('Individual', 'Stock'),
        ('Investment', 'Stock'),
        ('Investments', 'Stock'),
        ('JOINT WROS', 'Bonds'),
        ('L. MARTINEZ', 'Credit'),
        ('LemonBunny', 'Credit'),
        ('LendingClub', 'Loan'),
        ('LPFSA', 'Restricted Cash'),
        ('Marriott', 'Credit'),
        ('Other Property', 'Cash'),
        ('Preferred', 'Credit'),
        ('Property', 'Real Estate'),
        ('Quicksilver', 'Credit'),
        ('Rewards', 'Credit'),
        ('Roth IRA', 'Stock'),
        ('Savings', 'Cash'),
        ('Smart Saver', 'Stock'),
        ('Southest Business - Belinda', 'Credit'),
        ('Southwest Business - Luis', 'Credit'),
        ('TAXABLE Account', 'Stock'),
        ('TOTAL CHECKING', 'Cash'),
        ('Traditional IRA', 'Restricted Stock'),
        ('Visa', 'Credit'),
        ('Wallet', 'Crypto'),
        ('XXXXXX2351', 'Loan'),
    ]


def getConfig() -> Config:
  return Config()

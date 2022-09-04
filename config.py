from typing import List, Optional, Text


class Config:
    """A class capturing configurable settings for the mint scraper."""

    def __init__(self: 'Config') -> None:
        """Initializes the config to the default values.

        Properties:
          SKIPPED_ACCOUNTS: The account names are to be skipped when uploading to
            Google Sheets.
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
        self.SKIPPED_ACCOUNTS: List[Text] = [
            'Citi®\xa0Double Cash Card',
            'Citi® Double Cash Card',
            'Citi Double Cash Card',
            'Wells Fargo College Checking',
            'Total Checking',
        ]
        self.COLUMNS: List[Text] = [
            'fiData.date', 'fiData.inferredDescription', 'fiData.amount',
            'fiData.inferredCategory.name', 'accountRef.name', 'id']
        self.COLUMN_NAMES: List[Text] = [
            'Date', 'Merchant', 'Amount', 'Category', 'Account', 'ID']

        self.RAW_TRANSACTIONS_TITLE: Text = "Raw - All Transactions"
        self.RAW_ACCOUNTS_TITLE = 'Raw - All Accounts'
        self.SETTINGS_SHEET_TITLE: Text = 'Settings'
        self.WORKSHEET_TITLE: Text = "Transactions Worksheet"

        # Paid for Luis' Family's phones are not counted.
        # Ignore SCPD Payments.
        self.IGNORED_MERCHANTS: List[Text] = [
            'Anita Borg Institute',
            'Chase Autopay Ppd',
            'Chase Credit Crd Autopa',
            'Check',
            'Citi Autopay Payment We',
            'Citi Autopay Web',
            'City Of Nacogdoc',
            'Fairway Independent Mortgage Corp',
            'Federal Tax',
            'Foremost',
            'Graves Bail Bonds',
            'Healthequity Inc Healt',
            'Higher One Cornellu',
            'Internet Transfer From Interest Checking Account',
            'Project Fi',
            'Rental Income',
            'Stanford Cont Studies',
            'Stanford Scpd 6507253016 Ca',
            'Stanford Scpd Ca',
            'Stanford Scpd',
            'State Tax',
            'Treasury Direct Treas Drct',
            'Usforex',
            'Wealthfront Edi Pymnts',
            'Wealthfront Inc',
        ]
        # Credit card payments are redundant.
        self.IGNORED_CATEGORIES: List[Text] = [
            'Auto Payment',
            'Credit Card Payment',
            'Income',
            'Investments',
            'Mortgage  Rent',
            'Paycheck',
            'Taxes',
            'Transfer',
            'Federal Tax',
            'State Tax',
            'Rental Income',
            'Check',
            'Interest Income',
            'Financial',
            'Buy',
            'Loan Principal',
        ]
        # Merchant names are trimmed to at most these many characters.
        self.MAX_MERCHANT_NAME_CHARS: int = 20
        # We look back these many number of TXNs to identify the start date.
        self.NUM_TXN_FOR_CUTOFF: int = 400
        # Ignore specific transactions.
        self.IGNORED_TXNS: List[str] = [
            '75164122_2980191656_0',
            '75164122_2983818168_0',
            '75164122_2993888406_0',
            '75164122_2990478862_0',
            '75164122_3000221161_0',
            '75164122_3019178442_0',  # Banita stuff. Tracked separately.
            '75164122_3025617139_0',  # Transfer.
            '75164122_3036154626_0',  # Amex card.
        ]
        # If any merchant includes this in their name it is normalized to that value.
        self.MERCHANT_NORMALIZATION: List[str] = [
            'Advisor Autopilot',
            'Airbnb',
            'Amazoncom',
            'Attbill',
            'Audiblecom',
            'Blueapron',
            'Life Alive',
            'C T Wok',
            'Doordash',
            'Membership Fee',
            'Prime Video',
        ]

        # These IDs are the old version of Mint (v1). They aren't complete, but
        # we make our best guess.
        self.V1_IGNORED_TXNS: List[int] = [
            1246972549,
            1276304584,
            2461681673,
            2482214183,
            2504269103,
            2509775672,
            2510726212,
            2553593280,
            2553593281,
            2556300742,
            2559139111,
            2566235034,
            2573036964,
            2618759691,
            2651591652,
            2675570707,
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
            2902309919,
            2910459335,
            2917390750,
            2920747715,
            2920747716,
            2926069610,
            2926508879,
            2926508937,
            2940650110,
            2944077407,
            2945144150,
            2947546107,
            2949966496,
            2950201581,
            2952553369,
            2953522507,
            2953522508,
            2953522509,
            2953522510,
            2953805206,
            2953805219,
            2953805221,
            2959688556,
            2959688563,
            2959707325,
            2959707326,
            2959707327,
            2959707328,
            2960566083,
            2960566088,
            2960566089,
            2960566090,
            2960566091,
            2960986889,
            2963183492,
            2966202025,
            2966857485,
            2970848199,
            2972196882,
            2972706829,
            966664871,
        ]
        self.IMAP_SERVER: Optional[Text] = "imap.gmail.com"
        self.WAIT_FOR_ACCOUNT_SYNC: bool = True
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
            ('College-GiftAccount', 'Cash'),
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
            ('M&T Mortgage', 'Loan'),
            ('M1 Spend Plus', 'Cash'),
            ('Marriott', 'Credit'),
            ('META PLATFORMS', 'Stock'),
            ('Other Property', 'Cash'),
            ('Preferred', 'Credit'),
            ('Property', 'Real Estate'),
            ('Quicksilver', 'Credit'),
            ('Rewards', 'Credit'),
            ('Roth IRA', 'Stock'),
            ('Savings', 'Cash'),
            ('Smart Saver', 'Stock'),
            ('SpendAccount', 'Cash'),
            ('Southest Business - Belinda', 'Credit'),
            ('Southwest Business - Luis', 'Credit'),
            ('TAXABLE Account', 'Stock'),
            ('TOTAL CHECKING', 'Cash'),
            ('Traditional IRA', 'Restricted Stock'),
            ('Visa', 'Credit'),
            ('Wallet', 'Crypto'),
            ('XXXXXX2351', 'Loan'),
            ('XXXXX6055', 'Loan'),
            ('XXXXXX7338', 'Loan'),
        ]


def getConfig() -> Config:
    return Config()

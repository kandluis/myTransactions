from typing import List, Optional, Text


class Config:
    """A class capturing configurable settings for the scraper."""

    def __init__(self: "Config") -> None:
        """Initializes the config to the default values.

        Properties:
          CLEAN_UP_OLD_TXNS: If set to true, also cleans up txns already uploaded to
            sheets.
          SKIPPED_ACCOUNTS: The account names are to be skipped when uploading to
            Google Sheets.
          COLUMNS: The column names of the retrieved dataframe return by the
            Personal Capital library.
          COLUMN_NAMES: COLUMN_NAMES[i] is the column name in the Google sheet
            of the corresponding COLUMNs[i]
          UNIQUE_COLUMNs: These column names are used to uniquely identify txns
            insted of the txn id. This aids in de-duplicating accidentally
            duplicated txns from Mint API.
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
        self.COLUMNS: List[Text] = [
            "transactionDate",
            "merchant",
            "amount",
            "categoryName",
            "accountName",
            "userTransactionId",
            "description",
        ]
        self.COLUMN_NAMES: List[Text] = [
            "Date",
            "Merchant",
            "Amount",
            "Category",
            "Account",
            "ID",
            "Description",
        ]
        self.IDENTIFIER_COLUMNS = [
            "Account",
            "Amount",
            "Category",
            "Date",
            "Description",
            "Merchant",
        ]

        self.RAW_TRANSACTIONS_TITLE: Text = "Raw - All Transactions"
        self.RAW_ACCOUNTS_TITLE = "Raw - All Accounts"
        self.SETTINGS_SHEET_TITLE: Text = "Settings"
        self.WORKSHEET_TITLE: Text = "Transactions Worksheet"

        self.CLEAN_UP_OLD_TXNS: bool = False
        # After normalizations.
        self.SKIPPED_ACCOUNTS: List[Text] = [
            "Brokerage Ending In 5781",
            "CapitalOne Business Checking",
            "CapitalOne Business Savings Account",
            "Citi Double Cash Card Mom",
            "Everyday Checking Ending in 1557",
            "Fidelity Meta Platforms Inc 401K Plan",
            "Hsa Belinda",
            "Lending Account",
            "Visa Signature Business",
            "Way2save Savings Ending in 7505",
        ]

        # Paid for Luis' Family's phones are not counted.
        # Ignore SCPD Payments.
        self.IGNORED_MERCHANTS: List[Text] = [
            "Amzstorecrdpmt Payment",
            "Anita Borg Institute",
            "Chase Autopay",
            "Chase Credit Card",
            "Chase",
            "Check",
            "Citi Autopay Payment We",
            "Citi Autopay Web",
            "City Of Nacogdoc",
            "Fairway Independent Mortgage Corp",
            "Federal Tax",
            "Foremost",
            "Graves Bail Bonds",
            "Healthequity Inc Healt",
            "Higher One Cornellu",
            "Internet Transfer From Interest Checking Account",
            "Lendingclub Bank",
            "Preferred Item",
            "Project Fi",
            "Rental Income",
            "Stanford Cont Studies",
            "Stanford Scpd 6507253016 Ca",
            "Stanford Scpd Ca",
            "Stanford Scpd",
            "State Tax",
            "Treasury Direct Treas Drct",
            "Usforex",
            "Wealthfront Edi Pymnts",
            "Wealthfront Inc",
        ]
        # Credit card payments are redundant.
        self.IGNORED_CATEGORIES: List[Text] = [
            "Auto Payment",
            "Buy",
            "Check",
            "Credit Card Payment",
            "Credit Card Payments",
            "Federal Tax",
            "Financial",
            "Income",
            "Interest Income",
            "Investments",
            "Loan Payment",
            "Loan Principal",
            "Loans",
            "Mortgage",
            "Mortgages",
            "Paycheck",
            "Property Tax",
            "Rent",
            "Rental Income",
            "State Tax",
            "Taxes",
            "Transfer For Cash Spending",
            "Transfer",
            "Transfers",
        ]
        # We look back these many number of TXNs to identify the start date.
        self.NUM_TXN_FOR_CUTOFF: int = 1000
        # Ignore specific transactions.
        self.IGNORED_TXNS: List[str] = [
            "75164122_2980191656_0",
            "75164122_2983818168_0",
            "75164122_2993888406_0",
            "75164122_2990478862_0",
            "75164122_3000221161_0",
            "75164122_3019178442_0",  # Banita stuff. Tracked separately.
            "75164122_3036154626_0",  # Amex card.
            "75164122_3048334440_0",  # Transfer.
            "75164122_3051356816_0",  # NYC Trip Flight.
            "75164122_3065157443_0",  # NYC Hotel.
            "75164122_3061064481_0",  # Afrotech.
        ]
        # If any merchant includes this in their name is normalized to that value.
        self.MERCHANT_NORMALIZATION: List[str] = [
            "Advisor Autopilot",
            "Airbnb",
            "Amazoncom",
            "Attbill",
            "Audiblecom",
            "Blueapron",
            "C T Wok",
            "Doordash",
            "Life Alive",
            "Membership Fee",
            "Prime Video",
        ]

        self.IMAP_SERVER: Optional[Text] = "imap.gmail.com"
        self.WAIT_FOR_ACCOUNT_SYNC: bool = True
        self.ACCOUNT_NAME_TO_TYPE_MAP = [
            ("2125 Banita Street", "Real Estate"),
            ("2234 Ralmar Ave", "Real Estate"),
            ("401(K) SAVINGS PLAN", "Restricted Stock"),
            ("46 Barcelona St", "Real Estate"),
            ("529 College Plan", "Restricted Stock"),
            ("610-4 Pisgah Church Rd", "Real Estate"),
            ("Acorns", "Stock"),
            ("Ally", "Cash"),
            ("Amazon Prime", "Credit"),
            ("Apple", "Credit"),
            ("B Zeng - Ending in 2555", "Credit"),
            ("B. ZENG", "Credit"),
            ("Bank", "Cash"),
            ("Belinda and Luis", "Stock"),
            ("Brokerage", "Stock"),
            ("Build Wealth", "Stock"),
            ("C2012 RSU 10/05/2016 776.47 63 Class-C", "Stock"),
            ("Card", "Credit"),
            ("Cash", "Cash"),
            ("Chase Amazon - Luis", "Credit"),
            ("Chase Business Unlimited - Belinda", "Credit"),
            ("Chase Business Unlimited - Luis", "Credit"),
            ("Chase IHG - Luis", "Credit"),
            ("Chase United - Luis", "Credit"),
            ("Checking", "Cash"),
            ("Chris' 529 Account", "Restricted Stock"),
            ("Citi", "Credit"),
            ("College-GiftAccount", "Cash"),
            ("Credit", "Credit"),
            ("Deferred Comp", "Restricted Cash"),
            ("Discover", "Credit"),
            ("Equity Awards", "Stock"),
            ("ESPP_31003770405", "Stock"),
            ("FACEBOOK", "Stock"),
            ("Fidelity Roth", "Stock"),
            ("Freedom", "Credit"),
            ("Google Schwab Stock Awards", "Stock"),
            ("Google Vested Shares - Luis", "Stock"),
            ("GSU", "GOOG"),
            ("Health Savings", "Restricted Cash"),
            ("House in Mexico", "Real Estate"),
            ("HSA Investment", "Restricted Stock"),
            ("HSA", "Restricted Stock"),
            ("IHG - Belinda", "Credit"),
            ("Individual          ", "Stock"),
            ("Individual", "Stock"),
            ("Investment", "Stock"),
            ("Investments", "Stock"),
            ("JOINT WROS", "Bonds"),
            ("L. MARTINEZ", "Credit"),
            ("LemonBunny", "Credit"),
            ("Lending Account - Ending in 7687", "Loan"),
            ("Lending Account", "Loan"),
            ("LendingClub", "Loan"),
            ("Loancare", "Loan"),
            ("LPFSA", "Restricted Cash"),
            ("M&T Mortgage", "Loan"),
            ("M1 Spend Plus", "Cash"),
            ("Marriott", "Credit"),
            ("META PLATFORMS", "Stock"),
            ("Meta Schwab Stock Awards", "Stock"),
            ("Metamask", "Crypto"),
            ("Mr Cooper - Loan - Ending in 6055", "Loan"),
            ("Other Property", "Cash"),
            ("Preferred", "Credit"),
            ("Property", "Real Estate"),
            ("Quicksilver", "Credit"),
            ("Ralmar Loan", "Loan"),
            ("Rewards", "Credit"),
            ("Robinhood", "Stock"),
            ("Roth IRA", "Stock"),
            ("Savings", "Cash"),
            ("Securities", "Stock"),
            ("SEP IRA - Belinda", "Restricted Stock"),
            ("Smart Saver", "Stock"),
            ("Southest Business - Belinda", "Credit"),
            ("Southwest - Belinda", "Credit"),
            ("Southwest Business - Luis", "Credit"),
            ("SpendAccount", "Cash"),
            ("Staked", "Crypto"),
            ("TAXABLE Account", "Stock"),
            ("TOTAL CHECKING", "Cash"),
            ("Traditional IRA", "Restricted Stock"),
            ("United - Belinda", "Credit"),
            ("Vested Units", "Stock"),
            ("Visa", "Credit"),
            ("Wallet", "Crypto"),
            ("Waymo Vested", "Stock"),
            ("Wmu Awards", "Stock"),
            ("XXXXX6055", "Loan"),
            ("XXXXXX2351", "Loan"),
            ("XXXXXX7338", "Loan"),
        ]


# Global config.
GLOBAL = Config()

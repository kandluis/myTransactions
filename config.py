class Config:
    """A class capturing configurable settings for the scraper."""

    COLUMNS: list[str]
    COLUMN_NAMES: list[str]
    IDENTIFIER_COLUMNS: list[str]
    RAW_TRANSACTIONS_TITLE: str
    RAW_ACCOUNTS_TITLE: str
    SETTINGS_SHEET_TITLE: str
    WORKSHEET_TITLE: str
    CLEAN_UP_OLD_TXNS: bool
    SKIPPED_ACCOUNTS: list[str]
    IGNORED_MERCHANTS: list[str]
    IGNORED_CATEGORIES: list[str]
    NUM_TXN_FOR_CUTOFF: int
    PC_MIGRATION_DATE: str
    IGNORED_TXNS: list[str | int]
    MERCHANT_NORMALIZATION: list[str]
    ACCOUNT_NAME_TO_TYPE_MAP: list[tuple[str, str]]
    MERCHANT_NORMALIZATION_PAIRS: list[tuple[str, str]]
    STARTS_WITH_REMOVAL: list[str]
    ENDS_WITH_REMOVAL: list[str]

    def __init__(self: "Config") -> None:
        """Initializes the config to the default values.

        Properties:
          COLUMNS: The column names of the retrieved dataframe return by the
            Personal Capital library.
          COLUMN_NAMES: COLUMN_NAMES[i] is the column name in the Google sheet
            of the corresponding COLUMNs[i]
          IDENTIFIER_COLUMNS: These column names are used to uniquely identify txns
            insted of the txn id. This aids in de-duplicating accidentally
            duplicated txns from Mint API.

          RAW_SHEET_TITLE: The name of the sheet which contains the raw
            transactions.
          SETTINGS_SHEET_TITLE: The name of the sheet containing the setting
            page.
          WORKSHEET_TITLE: The title of the worksheet in Google Drive where
            transactions are uploaded.

          CLEAN_UP_OLD_TXNS: If set to true, also cleans up txns already uploaded to
            sheets.
          SKIPPED_ACCOUNTS: The account names are to be skipped when uploading to
            Google Sheets.
          IGNORED_MERCHANTS: A list of merchants which are filtered out when
            processing transactions.
          IGNORED_CATEGORIES: A list of categories which are filtered out when
            processing transactions.
          NUM_TXN_FOR_CUTOFF: The number of txns to update (if already on sheet).
          PC_MIGRATION_DATE: Migration date. All TXNs after this date are from PC.
          IGNORED_TXNS: A list of txns which are filtered out/skiped when uploading.

          MERCHANT_NORMALIZATION: If any merchant includes this in their name is
            normalized to that value.
          ACCOUNT_NAME_TO_TYPE_MAP: Maps account names to their type in google sheets.
          MERCHANT_NORMALIZATION_PAIRS: Names that cleaned up for merchants
            to disambiguate.
          STARTS_WITH_REMOVAL: If merchnt starts with this, remove the prefix.
          ENDS_WITH_REMOVAL: If merchands ends with this, remove the suffix.
        """
        self.COLUMNS = [
            "transactionDate",
            "merchant",
            "amount",
            "categoryName",
            "accountName",
            "userTransactionId",
            "description",
        ]
        self.COLUMN_NAMES = [
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

        self.RAW_TRANSACTIONS_TITLE = "Raw - All Transactions"
        self.RAW_ACCOUNTS_TITLE = "Raw - All Accounts"
        self.SETTINGS_SHEET_TITLE = "Settings"
        self.WORKSHEET_TITLE = "Transactions Worksheet"

        self.CLEAN_UP_OLD_TXNS = True
        self.SKIPPED_ACCOUNTS = [
            "360 Checking Ending In 8812",
            "Ally Joint Savings",
            "Brokerage Ending In 5781",
            "CapitalOne Business Checking",
            "CapitalOne Business Savings Account",
            "Citi Double Cash Card Mom",
            "Everyday Checking Ending in 1557",
            "Fidelity Meta Platforms Inc 401K Plan",
            "Hsa Belinda",
            "Lending Account",
            "Smartly Card Ending In 3855",
            "Sofi Savings",
            "Spark Cash Select Ending In 0527",
            "Visa Signature Business",
            "Way2save Savings Ending in 7505",
            "Wealthfront Cash Account",
        ]
        self.IGNORED_MERCHANTS = [
            "Amzstorecrdpmt Payment",
            "Anita Borg Institute",
            "Cardmember Services",
            "Chase Autopay",
            "Chase Credit Card",
            "Chase",
            "Check",
            "Citi Autopay Payment We",
            "Citi Autopay Web",
            "City Of Greensboro",
            "City Of Nacogdoc",
            "Fairway Independent Mortgage Corp",
            "Federal Tax",
            "Fi Beyond Pricing",
            "Foremost",
            "Graves Bail Bonds",
            "Healthequity Inc Healt",
            "Higher One Cornellu",
            "Internet Transfer From Interest Checking Account",
            "Lendingclub Bank",
            "Online Payment X To Danbury Court Hoa",
            "Optimum",
            "Palo Alto Park Mutual Water Co",
            "Preferred Item",
            "Project Fi",
            "Rental Income",
            "Sched Xfer Ref Fd",
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
        self.IGNORED_CATEGORIES = [
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
        self.NUM_TXN_FOR_CUTOFF = 300
        self.PC_MIGRATION_DATE = "2023-12-08"
        self.IGNORED_TXNS = [
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
            "75164122_3062515653_0",
            "75164122_3065157429_0",
            "75164122_3065157436_0",
            "75164122_3065157435_0",
            "75164122_3064336388_0",
            "75164122_3064336388_0",
            "75164122_3065157433_0",
            "75164122_3064336393_0",
            "75164122_3065963820_0",
            "75164122_3065963825_0",
            "75164122_3064098351_0",
            "75164122_3064098350_0",
            "75164122_3064098349_0",
            "75164122_3064336386_0",
            "75164122_3064336392_0",
            "75164122_3062356023_0",
            "75164122_3062356019_0",
            "75164122_3062356018_0",
            "75164122_3062356014_0",
            "75164122_3063109215_0",
            "75164122_3063109216_0",
            "75164122_3063204246_0",
            "75164122_3062356024_0",
            "75164122_3062356022_0",
            "75164122_3062356015_0",
            "75164122_3061251512_0",
            "75164122_3061913147_0",
            "75164122_3078843001_0",
            "75164122_3077181891_0",
            "75164122_3082822048_0",
            "75164122_3084025281_0",
            "75164122_3083448605_0",
            "75164122_3083448604_0",
            "75164122_3087634641_0",
            "75164122_3099119494_0",
            "75164122_3100885330_0",
            "75164122_18993200_2",
            "75164122_3098739436_0",
            "75164122_3121717579_0",
            "75164122_3146226972_0",
            "75164122_3164186642_0",
            "75164122_3165800658_0",
            "75164122_3173738558_0",
            "75164122_3179061933_0",
            "75164122_3179061809_0",
            "75164122_3179061788_0",
            "75164122_3179061871_0",
            "75164122_3179569625_0",
            "75164122_3188045443_0",
            "75164122_3188045489_0",
            "75164122_3188045440_0",
            "75164122_3188045440_0",
            "75164122_3188045437_0",
            "75164122_3188045433_0",
            "75164122_3179061751_0",
            "75164122_3183609679_0",
            "75164122_3188784645_0",
            "75164122_3188961827_0",
            "75164122_3190996810_0",
            "75164122_3192351458_0",
            "75164122_3194855702_0",
            "75164122_3194425999_0",
            "75164122_3196399766_0",
            "75164122_3196399767_0",
            "75164122_3196044002_0",
            "75164122_3202228007_0",
            "75164122_3202228044_0",
            "75164122_3202228023_0",
            "75164122_3202228050_0",
            "75164122_3198638221_0",
            "75164122_3199389879_0",
            "75164122_3198657680_0",
            "75164122_3198638220_0",
            "75164122_3198594462_0",
            "75164122_3198638219_0",
            "75164122_3198854812_0",
            "75164122_3198854816_0",
            "75164122_3199018466_0",
            "75164122_3198854814_0",
            "75164122_3199389876_0",
            "75164122_3199574678_0",
            "75164122_3199574680_0",
            "75164122_3199574679_0",
            "75164122_3200034424_0",
            "75164122_3200365548_0",
            "75164122_3200365547_0",
            "75164122_3200184545_0",
            "75164122_3210953404_0",
            "75164122_3210953405_0",
            "75164122_3218277094_0",
            "75164122_3215625424_0",
            "75164122_3179062025_0",
            "75164122_3220992524_0",
            "75164122_3217299130_0",
            "75164122_3211241318_0",
            1276304584,
            13636484313,
            13651952931,
            13662876082,
            13734306731,
            13827673871,
            13818533686,
            14023558380,
            13924957207,
            13924957209,
            13831696344,
            14155941148,
            14434608631,
            14527453101,
            14637610205,
            14606201462,
            14729235777,
            14790981702,
            14856023629,
            14885338449,
            15023588300,
            15106264860,
            15014933407,
            15123992672,
            15181622363,
            15276044358,
            15276044359,
            10000067310014,
            10000070757214,
            10000077933122,
            10000071286495,
            10000089804628,
            10000120894968,
            10000131888240,
            10000089036239,
            10000080098278,
            10000050453136,
            10000200465910,
            1015181622363,
            1015276044358,
            1015276044359,
            1015164634100,
            10000035767205,
            10000154779225,
            1015106264860,
            1015123992672,
            10000325230418,
            10000194122209,
            10000202278231,
            10000365855116,
            10000373177986,
            10000403123091,
            10000440802298,
            10000425039822,
            10000463928154,
            10000477314596,
            10000481047079,
            10000482031961,
            10000493040975,
        ]

        self.MERCHANT_NORMALIZATION = [
            "Advisor Autopilot",
            "Airbnb",
            "Amazon",
            "Amazoncom",
            "Attbill",
            "Audiblecom",
            "Blueapron",
            "C T Wok",
            "Chevron",
            "Chickfila",
            "Circle K",
            "Comcast",
            "Costco",
            "Disney Plus",
            "Dollar Tree",
            "Doordash",
            "Durham Sister",
            "Eonmobil",
            "Five Guys",
            "Groupon",
            "Happy Lamb",
            "Hertz",
            "In N Out",
            "Instacart",
            "Kura Revolving",
            "Life Alive",
            "Lucky",
            "Marina Food",
            "Mcdonalds",
            "Membership Fee",
            "Mod Pizza",
            "Onemedgoogle",
            "Palo Alto Gas",
            "Panda Express",
            "Panera Bread",
            "Prime Video",
            "Primepantry",
            "Starbucks",
            "Steam",
            "Super Yummy",
            "Sweetgreen",
            "Tancha",
            "Target",
            "Teaspoon",
            "Temucom",
            "The Body Shop",
            "The City Fish",
            "Uscustoms",
            "Walgreen",
            "Walmart",
            "Whole Foods",
        ]

        self.ACCOUNT_NAME_TO_TYPE_MAP = [
            ("2125 Banita St", "Real Estate"),
            ("2125 Banita Street", "Real Estate"),
            ("2234 Ralmar Ave", "Real Estate"),
            ("2234 Ralmar", "Real Estate"),
            ("401(K) SAVINGS PLAN", "Restricted Stock"),
            ("46 Barcelona St", "Real Estate"),
            ("529 College Plan", "Restricted Stock"),
            ("543 Hope St", "Real Estate"),
            ("610 Pisgah Church #4", "Real Estate"),
            ("610 Pisgah Church", "Real Estate"),
            ("610-4 Pisgah Church Rd", "Real Estate"),
            ("610-4 Pisgah Church", "Real Estate"),
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
            ("Fixed 15 Yr 1st Mortgage", "Loan"),
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
            ("Living Trust - Ending in 304", "Stock"),
            ("Loancare", "Loan"),
            ("LPFSA", "Restricted Cash"),
            ("M&T Mortgage", "Loan"),
            ("M1 Spend Plus", "Cash"),
            ("Marriott", "Credit"),
            ("META PLATFORMS", "Stock"),
            ("Meta Schwab Stock Awards", "Stock"),
            ("Metamask", "Crypto"),
            ("Mr Cooper - Loan - Ending in 6055", "Loan"),
            ("My Hawaiianmiles - Ending in 1643", "Credit"),
            ("My Hawaiianmiles - Ending in 7767", "Credit"),
            ("Other Property", "Cash"),
            ("Preferred", "Credit"),
            ("Property", "Real Estate"),
            ("Quicksilver", "Credit"),
            ("Ralmar Loan", "Loan"),
            ("Rewards", "Credit"),
            ("Robinhood", "Stock"),
            ("Roth Contributory Ira - Ending in 803", "Restricted Stock"),
            ("Roth IRA", "Stock"),
            ("Savings", "Cash"),
            ("Securities", "Stock"),
            ("Self Directed", "Stock"),
            ("SEP IRA - Belinda", "Restricted Stock"),
            ("Show More", "Stock"),
            ("Smart Saver", "Stock"),
            ("Smartly", "Credit"),
            ("Southest Business - Belinda", "Credit"),
            ("Southwest - Belinda", "Credit"),
            ("Southwest Business - Luis", "Credit"),
            ("SpendAccount", "Cash"),
            ("Spending Account", "Cash"),
            ("Staked", "Crypto"),
            ("TAXABLE Account", "Stock"),
            ("TOTAL CHECKING", "Cash"),
            ("Traditional IRA", "Restricted Stock"),
            ("Trust S&p 500 Direct Portfolio", "Stock"),
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

        self.MERCHANT_NORMALIZATION_PAIRS = [
            ("Amazoncom", "Amazon"),
            ("combill", ""),
            ("Grubhub ", ""),
            ("Nacogdoches Tx", ""),
            ("San Jose", ""),
            ("Saratoga", ""),
            ("Walmartcom", "Walmart"),
            ("Www", ""),
            ("Wholefds", "Whole Foods Market"),
            ("Elis I", "Elis"),
            ("Elis N", "Elis"),
            ("Targetcom", "Target"),
            ("Parteaspoon", "Teaspoon"),
        ]
        self.STARTS_WITH_REMOVAL = [
            "aplpay ",
            "gglpay ",
            "Tst ",
            "Square ",
            "Squ ",
            "Sq ",
        ]
        self.ENDS_WITH_REMOVAL = [
            " Ca",
        ]


# Global config.
GLOBAL = Config()

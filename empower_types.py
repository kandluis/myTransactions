from typing import Literal, TypedDict, Self, Optional


TChallengeMethod = Literal["OP", "TP", "TOTP"]


class SPHeaderBase(TypedDict):
    accountsMetaData: list[
        Literal["HAS_ON_US", "HAS_CASH", "HAS_INVESTMENT", "HAS_CREDIT"]
    ]
    authLevel: Literal["SESSION_AUTHENTICATED"]
    betaTester: bool
    developer: bool
    isDelegate: bool
    personId: int
    qualifiedLead: bool
    SP_HEADER_VERSION: int
    status: Literal["Active"]
    success: bool
    userGuid: str
    username: str
    userStage: str


class Error(TypedDict, total=False):
    code: int


class SPHeader(SPHeaderBase, total=False):
    csrf: str
    errors: list[Error]


class NextActionBase(TypedDict):
    action: Literal[
        "CLOSE_ACCOUNT",
        "UPDATE_STATUS_TO_BE_CLOSED_ACCOUNT",
        "MIGRATE_OAUTH",
        "INITIATE_REFRESH",
        "WAIT",
        "NONE",
    ]
    iconType: Literal["ERROR", "INFO", "AGGREGATING", "WARNING", "NONE"]
    prompts: list[str]


class NextAction(NextActionBase, total=False):
    aggregationErrorType: Literal["NO_ERROR", "MFA_REQUIRED", "AGENT_ERROR"]
    fastLinkFlow: Literal["EDIT", "REFRESH", "NONE"]
    nextActionMessage: str
    reportAction: Literal["NONE"]
    statusMessage: str


class AccountBase(TypedDict):
    accountId: str
    aggregating: bool
    # Date of account closure. If not closed, empty string.
    closedDate: str
    firmName: str
    is365DayTransactionEligible: bool
    isAccountUsedInFunding: bool
    isAsset: bool
    isCrypto: bool
    isEsog: bool
    isExcludeFromHousehold: bool
    isLiability: bool
    isManual: bool
    isManualPortfolio: bool
    isOAuth: bool
    isOnUs: bool
    isOnUs401K: bool
    isOnUsBank: bool
    isOnUsRetirement: bool
    isPartner: bool
    isPaymentFromCapable: bool
    isPaymentToCapable: bool
    isRefetchTransactionEligible: bool
    nextAction: NextAction
    originalFirmName: str
    paymentFromStatus: bool
    paymentToStatus: bool
    siteId: int
    userSiteId: int


class Trust(TypedDict, total=False):
    kindOfTrust: str
    kindOfTrustSecondary: str


class AdditionalAttributes(TypedDict, total=False):
    trust: Trust
    isCurrentEmployer: Literal["N", "Y"]
    jointAccountType: Literal["TENNANTS_IN_COMMON"]


AggregationError = TypedDict(
    "AggregationError",
    {
        "tags": list[Literal["PERSISTENT_ERROR", "UAR", "MFA_REQUIRED"]],
        "type": Literal["AGENT_ERROR", "MFA_REQUIRED"],
    },
)


class Account(AccountBase, total=False):
    account365DayTransactionProcessedDate: str  # mm/dd/yyyy
    accountHolder: str
    accountName: str
    accountNumber: str
    accountProperties: list[int]
    accountRefetchDate: str  # mm/dd/yyyy
    accountType: Literal[
        "401K",
        "401K, Former Employer",
        "529",
        "Assets",
        "Business",
        "Checking",
        "Credit",
        "Crypto Currency",
        "ESOP",
        "Individual Account",
        "Investment",
        "IRA - Roth",
        "IRA - Traditional",
        "Loan",
        "Mortgage",
        "Personal",
        "Savings",
        "SEP IRA",
    ]
    accountTypeGroup: Literal[
        "",
        "BANK",
        "CREDIT_CARD",
        "CRYPTO_CURRENCY",
        "EDUCATIONAL",
        "ESOP",
        "HEALTH",
        "INVESTMENT",
        "MORTGAGE",
        "RETIREMENT",
    ]
    accountTypeNew: Literal[
        "401K",
        "529",
        "BUSINESS",
        "CHECKING",
        "CRYPTO_CURRENCY",
        "ESOP",
        "HSA",
        "INVESTMENT",
        "IRA",
        "MORTGAGE",
        "PERSONAL",
        "SAVINGS",
    ]
    accountTypeSubtype: Literal["ROTH", "TRADITIONAL", "SEP"]
    accruedInterest: float
    additionalAttributes: AdditionalAttributes
    addressline: str
    adviceByMa: str
    advisoryFeePercentage: float
    advisoryFees: float
    aggregationError: AggregationError
    amountDue: float
    apr: float
    availableBalance: float
    availableCash: float
    availableCredit: float
    balance: float
    billingCycle: str
    city: str
    closedComment: str
    contactInfo: dict
    createdDate: int
    creditLimit: float
    creditUtilization: float
    currency: Literal["USD", ""]
    currentBalance: float
    customProductName: str
    defaultAdvisoryFee: float
    description: str
    disbursementType: str
    dueDate: int
    enrollmentConciergeRequested: bool
    excludeFromProposal: bool
    feesPerYear: float
    firstAggregationStartedDate: int
    fundFees: float
    hasProfitSharing: bool
    hasSponsorMatch: bool
    homeUrl: str
    infoSource: Literal["YODLEE", "SAFEPAGE"]
    interestRate: float
    is365DayTransactionProcessed: bool
    is401KEligible: bool
    isAccountNumberValidated: bool
    isAdvised: bool
    isCipOnHold: bool
    isCustomManual: bool
    isExcludeFromEmergencyFund: bool
    isHome: bool
    isIAVAccountNumberValid: bool
    isIAVEligible: bool
    isRoutingNumberValidated: bool
    isSelectedForTransfer: bool
    isStatementDownloadEligible: bool
    isTaxDeferredOrNonTaxable: bool
    isTransactionBasedSnapShotEligible: bool
    lastPayment: float
    lastPaymentAmount: float
    lastPaymentDate: int
    lastRefreshed: int
    latitude: float
    lender: str
    link: str
    loginFields: list[str]
    loginUrl: str
    logoPath: str
    longitude: float
    memo: str
    minPaymentDue: float
    name: str
    oldestTransactionDate: str  # yyyy-mm-dd
    originalName: str
    originationDate: int
    ownershipType: Literal["JOINT", "INDIVIDUAL"]
    payoffDate: int
    principalBalance: float
    priorBalance: float
    productId: int
    productType: Literal[
        "LOAN", "BANK", "CREDIT_CARD", "INVESTMENT", "OTHER_ASSETS", "MORTGAGE"
    ]
    propertyType: Literal["PRIMARY_RESIDENCE", "INVESTMENT_PROPERTY"]
    routingNumber: str
    runningBalance: float
    state: str
    totalFee: float
    treatedAsInvestment: bool
    treatedAsLoan: bool
    treatedAsMortgage: bool
    useHomeValuation: bool
    userAccountId: int
    userAccountName: str
    userProductId: int
    zillowStatus: Literal["NONE"]
    zip: str


class AccountsData(TypedDict):
    accounts: list[Account]
    assets: float
    cashAccountsTotal: float
    creditCardAccountsTotal: float
    investmentAccountsTotal: float
    liabilities: float
    loanAccountsTotal: float
    mortgageAccountsTotal: float
    networth: float
    otherAssetAccountsTotal: float
    otherLiabilitiesAccountsTotal: float


class TransactionBase(TypedDict):
    accountId: str
    accountName: str
    amount: float
    categoryId: int
    categoryName: str
    categoryType: Literal[
        "UNCATEGORIZE", "INCOME", "EXPENSE", "DEFERRED_COMPENSATION", "TRANSFER"
    ]
    currency: Literal["USD"]
    description: str
    hasViewed: bool
    includeInCashManager: bool
    isCashIn: bool
    isCashOut: bool
    isCost: bool
    isCredit: bool
    isDuplicate: bool
    isEditable: bool
    isIncome: bool
    isInterest: bool
    isNew: bool
    isSpending: bool
    originalAmount: float
    originalDescription: str
    price: float
    status: Literal["pending", "posted"]
    transactionDate: str  # yyyy-mm-dd
    transactionType: Literal[
        "Account Fee",
        "Buy",
        "Capital Gains Reinvest",
        "Contribution",
        "Credit",
        "Deposit Credits",
        "Dividend Received",
        "Interest",
        "LT CG Dist",
        "Payment",
        "Purchase",
        "Refund",
        "Reinvest Dividend",
        "ST CG Dist",
        "Stock Dividend",
        "Transfer",
        "Unknown",
    ]
    transactionTypeId: int
    userAccountId: int
    userTransactionId: int
    merchantId: str


class Transaction(TransactionBase, total=False):
    cusipNumber: str
    intermediary: str
    investmentType: Literal["Transfer", "Dividend", "Buy", "Sell"]
    merchant: str
    merchantType: Literal["SUBSCRIPTTION", "OTHERS", "BILLERS"]
    originalCategoryId: int
    quantity: float
    runningBalance: float
    simpleDescription: str
    subType: Literal[
        "CREDIT",
        "CREDIT_CARD_PAYMENT",
        "DEPOSIT",
        "DIRECT_DEPOSIT_SALARY",
        "INTEREST",
        "ONLINE_PURCHASE",
        "PAYMENT",
        "PURCHASE",
        "REFUND",
        "REWARDS",
        "TRANSFER",
        "UTILITIES_PAYMENT",
    ]
    symbol: int


class TransactionData(TypedDict):
    intervalType: Literal["WEEK"]
    endDate: str  # yyyy-mm-dd
    moneyIn: float
    transactions: list[Transaction]
    netCashflow: float
    averageOut: float
    moneyOut: float
    startDate: str  # yyyy-mm-dd
    averageIn: float


class Response(TypedDict):
    spHeader: SPHeader
    spData: AccountsData | TransactionData

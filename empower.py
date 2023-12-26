import mintotp
import requests
import getpass
import json
import re
import os

from dateutil.relativedelta import relativedelta
from datetime import datetime, date

from constants import TMFAMethod
from typing import cast, Mapping, Optional, Literal, get_args, TypedDict, Self
import logging


logger = logging.getLogger(__name__)


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


class PersonalCapitalSessionExpiredException(RuntimeError):
    pass


class PersonalCapital:
    _ROOT_URL: str = "https://home.personalcapital.com"
    _USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
    )
    _CHALLENGE_METHOD: dict[TMFAMethod, TChallengeMethod] = {
        "email": "OP",
        "phone": "OP",
        "sms": "OP",
        "totp": "TP",
    }
    _AUTH_ENDPOINT: dict[TMFAMethod, str] = {
        "email": "authenticateEmailByCode",
        "phone": "authenticatePhone",
        "sms": "authenticateSms",
        "totp": "authenticateTotpCode",
    }
    _AUTH_METHOD: dict[TMFAMethod, TChallengeMethod] = {
        "email": "OP",
        "phone": "OP",
        "sms": "OP",
        "totp": "TOTP",
    }

    _csrf: Optional[str]
    _email: Optional[str]  # Only set on successful login.
    session: requests.Session

    def __init__(self) -> None:
        self._csrf = None
        self._email = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": PersonalCapital._USER_AGENT})

    def _api_request(
        self, method: str, path: str, data: Mapping[str, str] = {}
    ) -> Response:
        response = self.session.request(
            method=method,
            url=os.path.join(PersonalCapital._ROOT_URL, path.lstrip("/")),
            data={**data, "csrf": self._csrf, "apiClient": "WEB"},
        )
        resp_txt = response.text

        is_json_resp = re.match(
            "text/json|application/json", response.headers.get("content-type", "")
        )

        if response.status_code != requests.codes.ok or not is_json_resp:
            logger.error(f"__api_request failed response: {resp_txt}")
            raise RuntimeError(
                f"Request for {path} {data} failed: \
                {response.status_code} {response.headers}"
            )

        json_res: Response = json.loads(resp_txt)

        if json_res.get("spHeader", {}).get("success", False) is False:
            resp_code = (
                json_res.get("spHeader", {}).get("errors", [{}])[0].get("code", None)
            )
            if resp_code == 201:
                self._csrf = None
                raise PersonalCapitalSessionExpiredException(
                    f'Login session expired {json_res["spHeader"]}'
                )
            raise RuntimeError(
                f'API request seems to have failed: {json_res["spHeader"]}'
            )

        return json_res

    def is_logged_in(self) -> bool:
        """Returns true if logged in."""
        if self._email is None:
            return False

        try:
            self.get_account_data()
            return True
        except PersonalCapitalSessionExpiredException:
            return False

    def get_transaction_data(
        self,
        start_date: date,
        end_date: date = datetime.now() + relativedelta(months=1),
    ) -> TransactionData:
        resp = self._api_request(
            "post",
            path="/api/transaction/getUserTransactions",
            data={
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
            },
        )
        return cast(TransactionData, resp["spData"])

    def get_account_data(self) -> AccountsData:
        resp = self._api_request("post", "/api/newaccount/getAccounts2")
        return cast(AccountsData, resp["spData"])

    def _handle_mfa(self, mfa_method: TMFAMethod, mfa_token: Optional[str]) -> None:
        """Handles MFA.

        Args:
            mfa_method: The method to use. Fully automated option is 'totp'.
                All other methods required some user input.
            mfa_token: The secret token to use. Required if mfa_method is 'totp',
                otherwise ignored.
        """
        challenge_endpoint = f"/api/credential/challenge{mfa_method.capitalize()}"
        challenge_data = {
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": PersonalCapital._CHALLENGE_METHOD[mfa_method],
            "bindDevice": "false",
        }
        self._api_request("post", challenge_endpoint, challenge_data)
        if mfa_method == "totp":
            if not mfa_token:
                raise ValueError(f"Specified mfa_method: {mfa_method} without token.")
            auth_data = {"totpCode": mintotp.totp(mfa_token, digest="sha512")}
        else:
            auth_data = {"code": getpass.getpass("Enter 2 factor code: ")}

        auth_endpoint = f"/api/credential/{PersonalCapital._AUTH_ENDPOINT[mfa_method]}"
        auth_data = {
            "challengeReason": "DEVICE_AUTH",
            "challengeMethod": PersonalCapital._AUTH_METHOD[mfa_method],
            "bindDevice": "false",
            **auth_data,
        }
        self._api_request("post", auth_endpoint, auth_data)

    def login(
        self,
        email: str,
        password: str,
        mfa_method: TMFAMethod = "totp",
        mfa_token: Optional[str] = None,
    ) -> Self:
        """
        Login using API calls.

        Args:
            email: The email (username) to use for logging in.
            password: The password for the account. Unencrypted.
            mfa_method: The MFA method to use for 2-factor. 'totp' is fully automated.
                The other methods required interactively inputting the generated code.
            mfa_token: Required if MFA method is 'totp'. This is the secret usd to
                generate the TOPT token.

        Returns:
            Instance of class after logging in.
        """
        if mfa_method not in get_args(TMFAMethod):
            raise ValueError(f"Auth method {mfa_method} is not supported")

        match = re.search(
            "csrf *= *'([-a-z0-9]+)'", self.session.get(PersonalCapital._ROOT_URL).text
        )
        if match is None:
            raise RuntimeError("Failed to extract csrf from session")
        self._csrf = match.groups()[0]

        identify_endpoint = "/api/login/identifyUser"
        identify_data = {"username": email}
        resp = self._api_request("post", identify_endpoint, identify_data)
        self._csrf = resp.get("spHeader", {}).get("csrf")

        if resp.get("spHeader", {}).get("authLevel") != "USER_REMEMBERED":
            self._handle_mfa(mfa_method, mfa_token)

        password_endpoint = "/api/credential/authenticatePassword"
        password_data = {
            "bindDevice": "false",
            "deviceName": "API script",
            "passwd": password,
        }
        resp = self._api_request("post", password_endpoint, password_data)

        self._email = email

        return self

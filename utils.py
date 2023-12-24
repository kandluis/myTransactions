import argparse
import os
from dataclasses import dataclass


from typing import Optional
from constants import TMFAMethod


def ConstructArgumentParser() -> argparse.ArgumentParser:
    """Constructs the argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Scrape mint for transaction data and upload to " "visualization."
    )
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--types",
        type=str,
        help='One of "all", "transactions", or "accounts" to specify what to ' "scrape",
        default="all",
    )
    parser.add_argument(
        "--cookies_path",
        type=str,
        default=None,
        help="The location of the cookies file to load and also update.",
    )
    return parser


class ScraperError(Exception):
    """Error raised by the scraper when an exception is encountered."""

    pass


@dataclass
class ScraperOptions:
    """Options on how to scrape mint.

    Properties:
      show_browser: bool, property specifying whether to show the brownser
      when logging into mint.
      scrape_transactions: bool. If true, we scrape txns. Default true.
      scrape_accounts: bool, if true, we scrape account data. Default true.
    """

    # When true, do all read operations but don't write data to sheets.
    dry_run: bool = False
    # When true, browser head is shown. Useful for debugging.
    show_browser: bool = False
    # When true, scrape txn data from Mint.
    scrape_transactions: bool = True
    # When true, scrape account data from Mint.
    scrape_accounts: bool = True
    # Path where we store the chrome session (speed up scraping).
    session_path: str = os.path.join(os.getcwd(), ".mintapi", "session")
    # MFA Method to use.
    mfa_method: TMFAMethod = "sms"
    # Required when using 'soft-token' method.
    mfa_token: Optional[str] = None
    # If set, expects chromedriver to be available in PATH.
    use_chromedriver_on_path = False
    # Only used when `use_chromedriver_on_path` is False. If so, this specifies
    # the directory where the latest version of chromedriver will be downloaded.
    chromedriver_download_path = os.getcwd()

    def __init__(self) -> None:
        """Initialize an options object. Options are the defaults."""
        pass

    @classmethod
    def fromArgsAndEnv(cls, args: argparse.Namespace) -> "ScraperOptions":
        """Initializes an options object from the given commandline
        arguments and environment variables.

        Args:
          args: The parsed arguments from the commandline from which to construct
          these options.

        Env:
          Reads environment variables.
        """
        types = args.types
        if types.lower() not in ["all", "accounts", "transactions"]:
            raise ScraperError("Type %s is not valid." % (types))

        options = ScraperOptions()
        options.dry_run = args.dry_run
        options.show_browser = args.debug
        options.scrape_transactions = (
            types.lower() == "all" or types.lower() == "transactions"
        )
        options.scrape_accounts = types.lower() == "all" or types.lower() == "accounts"

        options.session_path = os.getenv("CHROME_SESSION_PATH", options.session_path)
        options.mfa_method = "totp" if os.getenv("MFA_TOKEN") else "sms"
        options.mfa_token = os.getenv("MFA_TOKEN", options.mfa_token)
        options.use_chromedriver_on_path = os.getenv(
            "USE_CHROMEDRIVER_ON_PATH", default="False"
        ).lower() in ["true", "t", "1", "y", "yes"]
        options.chromedriver_download_path = os.getenv(
            "CHROMEDRIVER_PATH", options.chromedriver_download_path
        )

        return options

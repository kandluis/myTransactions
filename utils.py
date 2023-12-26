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
    return parser


class ScraperError(Exception):
    """Error raised by the scraper when an exception is encountered."""

    pass


@dataclass
class ScraperOptions:
    """Options on how to scrape Personal Capital.

    Properties:
      show_browser: bool, property specifying whether to show the brownser
      when logging into PC.
      scrape_transactions: bool. If true, we scrape txns. Default true.
      scrape_accounts: bool, if true, we scrape account data. Default true.
    """

    # When true, do all read operations but don't write data to sheets.
    dry_run: bool
    # When true, scrape txn data from Mint.
    scrape_transactions: bool
    # When true, scrape account data from Mint.
    scrape_accounts: bool
    # MFA Method to use.
    mfa_method: TMFAMethod
    # Required when using 'soft-token' method.
    mfa_token: Optional[str]

    def __init__(self) -> None:
        """Initialize an options object. Options are the defaults."""
        self.dry_run = False
        self.scrape_accounts = True
        self.scrape_transactions = True
        self.mfa_method = "sms"
        self.mfa_token = None

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
        options.scrape_transactions = (
            types.lower() == "all" or types.lower() == "transactions"
        )
        options.scrape_accounts = types.lower() == "all" or types.lower() == "accounts"

        options.mfa_method = "totp" if os.getenv("MFA_TOKEN") else "sms"
        options.mfa_token = os.getenv("MFA_TOKEN", options.mfa_token)

        return options

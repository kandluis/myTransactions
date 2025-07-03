import yaml
from typing import Any, Dict, List, Tuple


class Config:
    """A class capturing configurable settings for the scraper."""

    COLUMNS: List[str]
    COLUMN_NAMES: List[str]
    IDENTIFIER_COLUMNS: List[str]
    RAW_TRANSACTIONS_TITLE: str
    RAW_ACCOUNTS_TITLE: str
    SETTINGS_SHEET_TITLE: str
    WORKSHEET_TITLE: str
    CLEAN_UP_OLD_TXNS: bool
    SKIPPED_ACCOUNTS: List[str]
    IGNORED_MERCHANTS: List[str]
    IGNORED_CATEGORIES: List[str]
    NUM_TXN_FOR_CUTOFF: int
    PC_MIGRATION_DATE: str
    IGNORED_TXNS: List[str | int]
    MERCHANT_NORMALIZATION: List[str]
    ACCOUNT_NAME_TO_TYPE_MAP: List[Tuple[str, str]]
    MERCHANT_NORMALIZATION_PAIRS: List[Tuple[str, str]]
    STARTS_WITH_REMOVAL: List[str]
    ENDS_WITH_REMOVAL: List[str]

    def __init__(self: "Config") -> None:
        with open("config.yaml", "r") as f:
            config_data: Dict[str, Any] = yaml.safe_load(f)
        for key, value in config_data.items():
            setattr(self, key, value)


# Global config.
GLOBAL: Config = Config()

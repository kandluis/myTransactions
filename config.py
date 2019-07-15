import os

from typing import List, Optional, Text


class Config:
  """A class capturing configurable settings for the mint scraper.
  """

  def __init__(self: 'Config') -> None:
    """Initializes the config to the default values

    Properties:
      JOINT_SPENDING_ACCOUNTS: The account names which are held jointly.
        Only transactions from accounts matching these are uploaded to
        the Google Sheet.

      COLUMNS: The column names of the retrieved dataframe return by the 
        mintapi library.
      COLUMN_NAMES: COLUMN_NAMES[i] is the column name in the Google sheet
        of the corresponding COLUMNs[i]
      RAW_SHEET_TITLE: The name of the sheet which contains the raw transactions.
      KEYS_FILE: The file path (relative) of the keys to use when using the
        Google Sheets API
      WORKSHEET_TITLE: The title of the worksheet in Google Drive where
        transactions are uploaded.
      IGNORED_MERCHANTS: A list of merchants which are filtered out when
        processing transactions.
      IGNORED_CATEGORIES: A list of categories which are filtered out when
        processing transactions.
      SESSION_PATH: The full path to where Chrome session data can be stored and
        retrieved from.
      IMAP_SERVER: The IMAP server to use for MFA using email.

    """
    self.JOINT_SPENDING_ACCOUNTS: List[Text] = [
        'Spark Visa Signature Business', 'Amazon Card - Luis',
        'TOTAL_CHECKING', 'Citi - Personal', 'Preferred', 'Freedom - Belinda',
        'Mariott Rewards', 'Freedom Unlimited - Belinda', 'Freedom',
        'Amazon Store Card'
    ]
    self.COLUMNS: List[Text] = ['odate', 'mmerchant', 'amount', 'category']
    self.COLUMN_NAMES: List[Text] = ['Date', 'Merchant', 'Amount', 'Category']

    self.RAW_SHEET_TITLE: Text = "Raw - All Transactions"
    self.KEYS_FILE: Text = 'keys.json'
    self.WORKSHEET_TITLE: Text = "Transactions Worksheet"

    # Paid for Luis' Family's phones are not counted.
    # Ignore SCPD Payments.
    self.IGNORED_MERCHANTS: List[Text] = [
        'Project Fi', 'Stanford Scpd Ca', 'Stanford Scpd 6507253016 Ca',
        'Anita Borg Institute', 'Graves Bail Bonds'
    ]
    # Credit card payments are redundant.
    self.IGNORED_CATEGORIES: List[Text] = ['Credit Card Payment']
    self.SESSION_PATH: Optional[Text] = os.path.join(os.path.expanduser('~'),
                                                     ".mintapi", "session")
    self.IMAP_SERVER: Optional[Text] = "imap.gmail.com"


def getConfig() -> Config:
  return Config()
# We test several internal-only details. Its easier this way.
import remote
import pandas as pd
import pytest

from _pytest.monkeypatch import MonkeyPatch

from typing import Iterator


@pytest.fixture()
def config(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
  monkeypatch.setattr(remote.config.GLOBAL, "MERCHANT_NORMALIZATION", [])
  monkeypatch.setattr(remote.config.GLOBAL, "MAX_MERCHANT_NAME_CHARS", 100)
  yield monkeypatch


def test_normalize() -> None:
  assert remote._Normalize("Title String 123") == "Title String 123"
  assert remote._Normalize("title string 123") == "Title String 123"
  assert remote._Normalize("T$it^&le str90/4ing 123") == "Title Str904Ing 123"


def test_normalize_merchant(config: MonkeyPatch) -> None:
  assert remote._NormalizeMerchant("Normal Merchant") == "Normal Merchant"
  assert remote._NormalizeMerchant("wEirD CasES") == "Weird Cases"
  assert remote._NormalizeMerchant("  Extra   Spaces ") == "Extra Spaces"
  assert remote._NormalizeMerchant("Non-#%23&@(%C%*@4)ha$#2%(s") == "Nonchas"

  with config.context() as c:
    c.setattr(remote.config.GLOBAL, "MAX_MERCHANT_NAME_CHARS", 6)
    assert remote._NormalizeMerchant("Normal Merchant") == "Normal"
    # Spaces don't count.
    assert remote._NormalizeMerchant("Nor mal Merchant") == "Nor Mal"
    # Neither do special chars.
    assert remote._NormalizeMerchant(
        "N$%*@%*$or m$*%$a@$(%l Merchant") == "Nor Mal"

  with config.context() as c:
    c.setattr(
        remote.config.GLOBAL, "MERCHANT_NORMALIZATION", ["Airbnb", "Chipotle"])

    assert remote._NormalizeMerchant("Airbnb Long TxN 1234") == "Airbnb"
    assert remote._NormalizeMerchant(
        "Chi#$%$#%124potle Tx14x435") == "Chipotle"


def test_retrieve_accounts(monkeypatch, mocker) -> None:
  _MOCK_ACCOUNTS = [
      {'name': 'Amazon Store Card', 'value': 0.0, 'isActive': True},
      {'name': 'Amazon Store', 'value': 40723.74, 'isActive': True},
      {'name': 'Investment_101', 'value': 17950.9, 'isActive': True},
      {'name': 'Roth IRA', 'value': 32873.9, 'isActive': True},
      {'name': 'LendingClub', 'value': 957.39, 'isActive': True},
      # Will be dropped because it's not active.
      {'name': 'GOOGLE INC.', 'value': 58447.76, 'isActive': False},
      {'name': 'Brokerage Account', 'value': 0.0, 'isActive': True},
      {'name': 'Brokerage Account - Luis', 'value': 0.0, 'isActive': True},
      {'name': 'Traditional IRA', 'value': 0.0, 'isActive': True}
  ]
  # We should match more specific to least specific.
  monkeypatch.setattr(remote.config.GLOBAL, 'ACCOUNT_NAME_TO_TYPE_MAP', [
      # Won't match anything.
      ('Amazon', 'Savings'),
      ('Amazon Store Card', 'Credit'),
      ('Amazon Store', 'Checking'),
      ('Investment', 'Investment'),
      # Case should not matter.
      ('roth', 'Investment'),
      ('Lending', 'Loan'),
      ('Brokerage', 'Stock'),
      ('Brokerage account - luis', 'Retirement'),
      # (Traditional, Other)
  ])
  mockMintApi = mocker.MagicMock()
  mockMintApi.get_account_data.return_value = _MOCK_ACCOUNTS

  data = remote.RetrieveAccounts(mockMintApi)
  data.sort_values(by=['Name'], inplace=True, ignore_index=True)
  expected = pd.DataFrame([
      # Sorted by name.
      {'Name': 'Amazon Store', 'Type': 'Checking', 'Balance': 40723.74},
      {'Name': 'Amazon Store Card', 'Type': 'Credit', 'Balance': 0.0},
      {'Name': 'Brokerage Account', 'Type': 'Stock', 'Balance': 0.0},
      {'Name': 'Brokerage Account - Luis', 'Type': 'Retirement',
       'Balance': 0.0},
      {'Name': 'Investment_101', 'Type': 'Investment', 'Balance': 17950.9},
      {'Name': 'LendingClub', 'Type': 'Loan', 'Balance': 957.39},
      {'Name': 'Roth IRA', 'Type': 'Investment', 'Balance': 32873.9},
      {'Name': 'Traditional IRA', 'Type': 'Unknown - Traditional IRA',
       'Balance': 0.0}
  ])
  assert data.compare(expected).empty

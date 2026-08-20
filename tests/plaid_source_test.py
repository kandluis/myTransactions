import pandas as pd
import pytest

import plaid_source


class FakeWorksheet:
    def __init__(self):
        self.values = {}
        self.hidden = False

    def get_value(self, cell):
        return self.values.get(cell, "")

    def update_values(self, cell, values):
        start_row = int(cell[1:])
        for offset, value in enumerate(values):
            self.values[f"A{start_row + offset}"] = value[0]

    def get_values(self, start, end, include_tailing_empty=False):
        start_row = int(start[1:])
        end_row = int(end[1:])
        return [
            [self.values.get(f"A{row}", "")] for row in range(start_row, end_row + 1)
        ]


class FakeSheet:
    def __init__(self):
        self.ws = FakeWorksheet()
        self.exists = False

    def worksheet_by_title(self, title):
        if not self.exists:
            raise KeyError(title)
        return self.ws

    def add_worksheet(self, title, rows, cols):
        self.exists = True
        return self.ws


def test_state_is_encrypted_and_round_trips(monkeypatch):
    monkeypatch.setenv("PLAID_STATE_KEY", "a test state key")
    sheet = FakeSheet()
    store = plaid_source.SheetStateStore(sheet)

    store.save({"version": 1, "items": {"item": {"access_token": "secret"}}})

    assert "secret" not in sheet.ws.values[plaid_source.STATE_CELL]
    assert store.load()["items"]["item"]["access_token"] == "secret"
    assert sheet.ws.hidden is True


def test_large_state_is_split_across_encrypted_cells(monkeypatch):
    monkeypatch.setenv("PLAID_STATE_KEY", "a test state key")
    sheet = FakeSheet()
    store = plaid_source.SheetStateStore(sheet)
    payload = "x" * (plaid_source.STATE_MAX_CHUNK_SIZE * 2)

    store.save({"version": 1, "items": {"item": {"pending": payload}}})

    assert sheet.ws.values["A3"]
    assert store.load()["items"]["item"]["pending"] == payload


def test_smaller_state_clears_stale_encrypted_chunks(monkeypatch):
    monkeypatch.setenv("PLAID_STATE_KEY", "a test state key")
    sheet = FakeSheet()
    store = plaid_source.SheetStateStore(sheet)
    large_payload = "x" * (plaid_source.STATE_MAX_CHUNK_SIZE * 2)

    store.save({"version": 1, "items": {"item": {"pending": large_payload}}})
    store.save({"version": 1, "items": {"item": {"status": "active"}}})

    assert sheet.ws.values["A3"] == ""
    assert store.load()["items"]["item"]["status"] == "active"


def test_state_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("PLAID_STATE_KEY", "first key")
    sheet = FakeSheet()
    store = plaid_source.SheetStateStore(sheet)
    store.save({"version": 1, "items": {}})
    monkeypatch.setenv("PLAID_STATE_KEY", "second key")

    with pytest.raises(plaid_source.PlaidError, match="cannot be decrypted"):
        store.load()


def test_transaction_sign_mapping_and_overlap_deduplication():
    item = {"selected_account_ids": ["acct"], "account_mappings": {"acct": "Smartly"}}
    incoming = plaid_source.transaction_frame(
        [
            {
                "account_id": "acct",
                "transaction_id": "one",
                "date": "2026-08-01",
                "amount": 12.50,
                "merchant_name": "Coffee Shop",
                "name": "Coffee Shop",
            }
        ],
        item,
    )
    assert incoming.iloc[0]["Amount"] == -12.50
    existing = incoming.copy()
    existing.loc[0, "ID"] = "legacy-id"
    merged = plaid_source.merge_transactions(existing, incoming, set(), set())
    assert len(merged) == 1


def test_plaid_transaction_frame_filters_amex_autopay_payment():
    item = {"selected_account_ids": ["acct"], "account_mappings": {"acct": "Amex"}}

    incoming = plaid_source.transaction_frame(
        [
            {
                "account_id": "acct",
                "transaction_id": "payment",
                "date": "2026-08-03",
                "amount": 1012.93,
                "merchant_name": "Autopay Payment Thank You",
                "name": "Autopay Payment Thank You",
            }
        ],
        item,
    )

    assert incoming.empty


def test_modified_and_removed_ids_replace_only_plaid_rows():
    existing = pd.DataFrame(
        [
            {
                "Date": "2026-08-01",
                "Merchant": "A",
                "Amount": -1,
                "Category": "X",
                "Account": "One",
                "ID": "plaid:old",
                "Description": "A",
            },
            {
                "Date": "2026-08-02",
                "Merchant": "B",
                "Amount": -2,
                "Category": "X",
                "Account": "One",
                "ID": "legacy",
                "Description": "B",
            },
        ]
    )
    merged = plaid_source.merge_transactions(
        existing, pd.DataFrame(columns=existing.columns), {"plaid:old"}, set()
    )
    assert merged["ID"].tolist() == ["legacy"]


def test_reconciliation_reports_overlap_and_new_candidates():
    existing = pd.DataFrame(
        [
            {
                "Date": "2026-08-01",
                "Merchant": "A",
                "Amount": -1,
                "Category": "X",
                "Account": "One",
                "ID": "old",
                "Description": "A",
            }
        ]
    )
    candidate = pd.concat(
        [existing, existing.assign(Date="2026-08-02")], ignore_index=True
    )
    result = plaid_source.reconcile(existing, candidate)
    assert result["matched_overlap"] == 1
    assert result["plaid_only_candidates"] == 1

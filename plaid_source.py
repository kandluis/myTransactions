"""Plaid Transactions Sync source and encrypted Google Sheet state.

The spreadsheet is deliberately the durable store: both Fly process groups can
read it, while the value kept there is an authenticated encrypted blob.  The
only key material lives in ``PLAID_STATE_KEY``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import pandas as pd
import requests
from cryptography.fernet import Fernet, InvalidToken

import config
import remote
import utils

STATE_SHEET_TITLE = "Plaid State"
STATE_CELL = "A2"
STATE_MAX_CHUNK_SIZE = 45_000
STATE_MAX_CHUNKS = 200
MAX_ITEMS = 10
RESERVED_ITEMS = 1


class PlaidError(utils.ScraperError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def is_configured() -> bool:
    return bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET"))


def _fernet() -> Fernet:
    key = os.getenv("PLAID_STATE_KEY", "")
    if not key:
        raise PlaidError("state_decryption_failed", "PLAID_STATE_KEY is not configured")
    # Accept a normal secret as well as Fernet's urlsafe base64 form.  This
    # makes deployment secrets less error prone without weakening encryption.
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(derived)


class SheetStateStore:
    def __init__(self, spreadsheet: Any):
        self.spreadsheet = spreadsheet

    def _worksheet(self) -> Any:
        try:
            return self.spreadsheet.worksheet_by_title(title=STATE_SHEET_TITLE)
        except Exception:
            ws = self.spreadsheet.add_worksheet(STATE_SHEET_TITLE, rows=10, cols=2)
            ws.update_values("A1", [["Encrypted Plaid state - do not edit"]])
            # pygsheets exposes this on Worksheet in supported versions.  It is
            # best-effort to retain compatibility with old local installations.
            try:
                ws.hidden = True
            except Exception:
                pass
            return ws

    def load(self) -> dict[str, Any]:
        try:
            worksheet = self._worksheet()
            if hasattr(worksheet, "get_values"):
                cells = worksheet.get_values(
                    "A2", f"A{STATE_MAX_CHUNKS + 1}", include_tailing_empty=False
                )
                raw = "".join(str(row[0]) for row in cells if row and row[0]).strip()
            else:  # Small test doubles and old pygsheets versions.
                raw = str(worksheet.get_value(STATE_CELL) or "").strip()
            if not raw:
                return {"version": 1, "items": {}}
            data = _fernet().decrypt(raw.encode())
            value = json.loads(data.decode())
            if not isinstance(value, dict) or not isinstance(
                value.get("items", {}), dict
            ):
                raise ValueError("invalid state shape")
            return value
        except InvalidToken as exc:
            raise PlaidError(
                "state_decryption_failed", "Plaid state cannot be decrypted"
            ) from exc
        except PlaidError:
            raise
        except Exception as exc:
            raise PlaidError(
                "state_decryption_failed", "Plaid state could not be read"
            ) from exc

    def save(self, state: dict[str, Any]) -> None:
        encrypted = (
            _fernet()
            .encrypt(json.dumps(state, separators=(",", ":")).encode())
            .decode()
        )
        chunks = [
            encrypted[offset : offset + STATE_MAX_CHUNK_SIZE]
            for offset in range(0, len(encrypted), STATE_MAX_CHUNK_SIZE)
        ]
        if len(chunks) >= STATE_MAX_CHUNKS:
            raise PlaidError(
                "state_decryption_failed", "Plaid state is too large to store"
            )
        # The last blank value clears a stale trailing chunk from an earlier,
        # larger state write. Each individual Sheet cell remains below 50k.
        self._worksheet().update_values(
            STATE_CELL, [[chunk] for chunk in chunks] + [[""]]
        )


class PlaidClient:
    def __init__(self) -> None:
        env = os.getenv("PLAID_ENV", "production")
        base_url = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }.get(env)
        if base_url is None:
            raise PlaidError(
                "sync_failed", "PLAID_ENV must be sandbox, development, or production"
            )
        self.base_url: str = base_url

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "client_id": os.getenv("PLAID_CLIENT_ID", ""),
            "secret": os.getenv("PLAID_SECRET", ""),
            **body,
        }
        try:
            response = requests.post(self.base_url + path, json=payload, timeout=45)
            data = response.json()
        except requests.RequestException as exc:
            raise PlaidError("sync_failed", "Plaid request failed") from exc
        except ValueError as exc:
            raise PlaidError(
                "sync_failed", "Plaid returned an invalid response"
            ) from exc
        if not response.ok:
            code = str(data.get("error_code", "sync_failed"))
            if code in {"ITEM_LOGIN_REQUIRED", "ITEM_LOCKED", "ITEM_NOT_SUPPORTED"}:
                raise PlaidError(
                    "reauthentication_required",
                    "A Plaid connection needs to be reauthenticated",
                )
            raise PlaidError(
                "sync_failed", str(data.get("error_message", "Plaid request failed"))
            )
        return data

    def create_link_token(
        self, *, update_access_token: Optional[str] = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "user": {"client_user_id": "mytransactions"},
            "client_name": "My Transactions",
            "products": ["transactions"],
            "country_codes": ["US"],
            "language": "en",
            "transactions": {"days_requested": 90},
        }
        redirect = os.getenv("PLAID_REDIRECT_URI", "")
        if redirect:
            body["redirect_uri"] = redirect
        if update_access_token:
            body["access_token"] = update_access_token
        return self._post("/link/token/create", body)

    def exchange_public_token(self, public_token: str) -> dict[str, Any]:
        return self._post("/item/public_token/exchange", {"public_token": public_token})

    def sync(
        self, access_token: str, cursor: str = ""
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
        added: list[dict[str, Any]] = []
        modified: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        has_more = True
        next_cursor = cursor
        while has_more:
            data = self._post(
                "/transactions/sync",
                {"access_token": access_token, "cursor": next_cursor, "count": 500},
            )
            added.extend(data.get("added", []))
            modified.extend(data.get("modified", []))
            removed.extend(data.get("removed", []))
            next_cursor = str(data.get("next_cursor", ""))
            has_more = bool(data.get("has_more"))
        return added, modified, removed, next_cursor

    def accounts(self, access_token: str) -> list[dict[str, Any]]:
        return self._post("/accounts/get", {"access_token": access_token}).get(
            "accounts", []
        )


def _account_name(account: dict[str, Any], item: dict[str, Any]) -> str:
    mappings = item.get("account_mappings", {})
    return str(
        mappings.get(
            account["account_id"],
            account.get("name") or account.get("official_name") or "Unknown Account",
        )
    )


def transaction_frame(
    transactions: Iterable[dict[str, Any]], item: dict[str, Any]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    selected = set(item.get("selected_account_ids", []))
    for txn in transactions:
        if selected and txn.get("account_id") not in selected:
            continue
        # Plaid positive amount is money leaving the account; this project uses
        # negative values for spend, matching the established Empower output.
        amount = -float(txn.get("amount", 0))
        merchant = txn.get("merchant_name") or txn.get("name") or ""
        category = (txn.get("personal_finance_category") or {}).get(
            "primary"
        ) or "Uncategorized"
        rows.append(
            {
                "Date": txn.get("date", ""),
                "Merchant": merchant,
                "Amount": amount,
                "Category": category,
                "Account": _account_name(txn, item),
                "ID": "plaid:" + str(txn.get("transaction_id", "")),
                "Description": txn.get("name") or merchant,
            }
        )
    frame = pd.DataFrame(rows, columns=config.GLOBAL.COLUMN_NAMES)
    if frame.empty:
        return frame
    return remote._cleanTxns(remote.ApplyCategoryRules(frame))


def overlap_fingerprint(row: pd.Series) -> str:
    return "|".join(
        [
            str(row.get("Account", "")).strip().lower(),
            str(row.get("Date", "")),
            f"{float(row.get('Amount', 0)):.2f}",
            str(row.get("Description", row.get("Merchant", ""))).strip().lower(),
        ]
    )


def reconcile(existing: pd.DataFrame, candidate: pd.DataFrame) -> dict[str, int]:
    existing_fps = (
        existing.apply(overlap_fingerprint, axis=1)
        if not existing.empty
        else pd.Series(dtype=str)
    )
    existing_counts = existing_fps.value_counts()
    candidate_fps = (
        candidate.apply(overlap_fingerprint, axis=1)
        if not candidate.empty
        else pd.Series(dtype=str)
    )
    return {
        "matched_overlap": int(candidate_fps.isin(existing_counts.index).sum()),
        "plaid_only_candidates": int(
            (~candidate_fps.isin(existing_counts.index)).sum()
        ),
        "ambiguous_matches": int(
            candidate_fps.map(existing_counts).fillna(0).gt(1).sum()
        ),
        "account_mapping_gaps": (
            int(candidate["Account"].eq("Unknown Account").sum())
            if not candidate.empty
            else 0
        ),
    }


def merge_transactions(
    existing: pd.DataFrame,
    additions: pd.DataFrame,
    modified_ids: set[str],
    removed_ids: set[str],
) -> pd.DataFrame:
    result = existing.copy()
    if "ID" in result:
        result = result[~result["ID"].isin(removed_ids | modified_ids)]
    if not additions.empty:
        current_fps = set(result.apply(overlap_fingerprint, axis=1))
        additions = additions[
            ~additions.apply(overlap_fingerprint, axis=1).isin(current_fps)
        ]
        result = pd.concat([result, additions], ignore_index=True)
    return result.sort_values("Date", ascending=True, ignore_index=True)


def initial_window_start() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=90)).isoformat()

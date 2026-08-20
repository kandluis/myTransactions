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
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Hashable, Iterable, Optional

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
                chunks = []
                for row in cells:
                    if not row or not row[0]:
                        break
                    chunks.append(str(row[0]))
                raw = "".join(chunks).strip()
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
        if len(chunks) > STATE_MAX_CHUNKS:
            raise PlaidError(
                "state_decryption_failed", "Plaid state is too large to store"
            )
        # Clear every remaining state cell so a later, smaller save cannot leave
        # encrypted fragments that a future read might accidentally consume.
        self._worksheet().update_values(
            STATE_CELL,
            [[chunk] for chunk in chunks] + [[""]] * (STATE_MAX_CHUNKS - len(chunks)),
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
    merchant_or_description = str(row.get("Merchant") or row.get("Description", ""))
    return "|".join(
        [
            remote._Normalize(str(row.get("Account", ""))).lower(),
            str(row.get("Date", "")),
            f"{float(row.get('Amount', 0)):.2f}",
            remote._NormalizeMerchant(merchant_or_description).lower(),
        ]
    )


def _overlap_components(row: pd.Series) -> tuple[str, float, str]:
    """Return the stable portions of an initial-import overlap key."""
    aliases = getattr(config.GLOBAL, "HISTORICAL_ACCOUNT_ALIASES", {})
    account = str(row.get("Account", ""))
    canonical_account = aliases.get(account, account)
    return (
        remote._Normalize(canonical_account).lower(),
        round(float(row.get("Amount", 0)), 2),
        _overlap_merchant(row),
    )


def _overlap_merchant(row: pd.Series) -> str:
    merchant_or_description = str(row.get("Merchant") or row.get("Description", ""))
    return remote._NormalizeMerchant(merchant_or_description).lower()


def _merchants_overlap(left: str, right: str) -> bool:
    """Allow only conservative label variations between transaction sources."""
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) >= 4 and (left in right or right in left):
        return True
    left_tokens = set(re.findall(r"[a-z0-9]+", left))
    right_tokens = set(re.findall(r"[a-z0-9]+", right))
    shared_tokens = left_tokens & right_tokens
    return (
        len(shared_tokens) >= 2
        and len(shared_tokens) >= min(len(left_tokens), len(right_tokens)) / 2
    )


def _tolerant_overlap_pairs(
    existing: pd.DataFrame, candidate: pd.DataFrame, max_date_delta_days: int = 3
) -> list[tuple[int, Hashable, Hashable]]:
    """Return all conservative candidate/history overlap pairs."""
    if existing.empty or candidate.empty:
        return []

    old = existing.copy()
    new = candidate.copy()
    old["_overlap_date"] = pd.to_datetime(old["Date"], errors="coerce")
    new["_overlap_date"] = pd.to_datetime(new["Date"], errors="coerce")
    old = old[old["_overlap_date"].notna()]
    new = new[new["_overlap_date"].notna()]

    buckets: dict[tuple[str, float], list[tuple[Hashable, pd.Timestamp, str]]] = {}
    for old_index, row in old.iterrows():
        account, amount, merchant = _overlap_components(row)
        buckets.setdefault((account, amount), []).append(
            (old_index, row["_overlap_date"], merchant)
        )

    possible: list[tuple[int, Hashable, Hashable]] = []
    for new_index, row in new.iterrows():
        account, amount, merchant = _overlap_components(row)
        for old_index, old_date, old_merchant in buckets.get((account, amount), []):
            date_delta = abs((row["_overlap_date"] - old_date).days)
            merchant_matches = _merchants_overlap(merchant, old_merchant)
            # A fuzzy provider-label match is only safe across an adjacent
            # posting date; exact labels retain the established three-day
            # window for pending/posted timing differences.
            allowed_date_delta = max_date_delta_days if merchant == old_merchant else 1
            if date_delta <= allowed_date_delta and merchant_matches:
                possible.append((date_delta, new_index, old_index))
    return possible


def tolerant_overlap_matches(
    existing: pd.DataFrame, candidate: pd.DataFrame, max_date_delta_days: int = 3
) -> list[tuple[Hashable, Hashable]]:
    """Match initial-import rows to existing history, once each.

    Empower and Plaid can assign adjacent posting dates to the same settled
    card transaction.  The match includes a configured historical account
    alias, amount, a small date window, and conservative merchant comparison.
    Each row is consumed at most once so repeated same-value purchases remain.
    """

    matched_new: set[Hashable] = set()
    matched_old: set[Hashable] = set()
    matches: list[tuple[Hashable, Hashable]] = []
    for _, new_index, old_index in sorted(
        _tolerant_overlap_pairs(existing, candidate, max_date_delta_days)
    ):
        if new_index in matched_new or old_index in matched_old:
            continue
        matched_new.add(new_index)
        matched_old.add(old_index)
        matches.append((old_index, new_index))
    return matches


def reconcile(existing: pd.DataFrame, candidate: pd.DataFrame) -> dict[str, int]:
    matches = tolerant_overlap_matches(existing, candidate)
    # A candidate with more than one otherwise-valid historical row deserves
    # review, even though the one-to-one matcher chooses the nearest row.
    possible_counts: dict[Hashable, int] = {}
    for _, candidate_index, _ in _tolerant_overlap_pairs(existing, candidate):
        possible_counts[candidate_index] = possible_counts.get(candidate_index, 0) + 1
    return {
        "matched_overlap": len(matches),
        "plaid_only_candidates": len(candidate) - len(matches),
        "ambiguous_matches": sum(count > 1 for count in possible_counts.values()),
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
    *,
    initial_import: bool = False,
) -> pd.DataFrame:
    result = existing.copy()
    if "ID" in result:
        result = result[~result["ID"].isin(removed_ids | modified_ids)]
    if not additions.empty:
        if initial_import:
            matched_additions = {
                addition_index
                for _, addition_index in tolerant_overlap_matches(result, additions)
            }
            additions = additions.drop(index=list(matched_additions))
        else:
            current_fps = set(result.apply(overlap_fingerprint, axis=1))
            additions = additions[
                ~additions.apply(overlap_fingerprint, axis=1).isin(current_fps)
            ]
        result = pd.concat([result, additions], ignore_index=True)
    return result.sort_values("Date", ascending=True, ignore_index=True)


def initial_window_start() -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=90)).isoformat()

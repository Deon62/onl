"""A merchant's payout accounts, kept in `merchants.settlement` as {"accounts": [...], "default_id": ...}.

The default account is mirrored onto merchants.payout_method / payout_destination, which payouts read.
"""

import uuid
from datetime import UTC, datetime

from app.errors import ApiError
from app.models import Merchant
from app.models.enums import PayoutMethod

DETAIL_KEYS = ("phone", "till", "paybill", "paybill_account", "bank_name", "bank_branch", "account_name", "account_number")
MAX_ACCOUNTS = 5


def destination_for(method: str, d: dict) -> str:
    """Display/remittance string, matching the dashboard's destinationFor()."""
    if method == PayoutMethod.MPESA:
        return d["phone"]
    if method == PayoutMethod.TILL:
        return f"Till {d['till']}"
    if method == PayoutMethod.PAYBILL:
        return f"Paybill {d['paybill']} · Acc {d['paybill_account']}"
    return f"{d['bank_name']} - A/C ****{d['account_number'][-4:]}"


def validate_details(method: str, d: dict) -> None:
    def bad(field: str, msg: str):
        raise ApiError(422, "invalid_account", msg, {"field": field})

    if method == PayoutMethod.MPESA and not d.get("phone"):
        bad("phone", "Enter the M-Pesa phone number.")
    if method == PayoutMethod.TILL and not (5 <= len(d.get("till", "")) <= 7):
        bad("till", "Till numbers are 5 to 7 digits.")
    if method == PayoutMethod.PAYBILL:
        if not (5 <= len(d.get("paybill", "")) <= 7):
            bad("paybill", "Paybill numbers are 5 to 7 digits.")
        if not d.get("paybill_account"):
            bad("paybill_account", "Enter the Paybill account number.")
    if method == PayoutMethod.BANK:
        if not d.get("bank_name"):
            bad("bank_name", "Select a bank.")
        if not d.get("account_name"):
            bad("account_name", "Enter the account name.")
        num = d.get("account_number", "").replace(" ", "")
        if not (num.isdigit() and 6 <= len(num) <= 20):
            bad("account_number", "Bank account numbers are 6 to 20 digits.")


def accounts_of(m: Merchant) -> tuple[list[dict], str | None]:
    """The account list and default id. Merchants saved before multi-account support get their one account listed."""
    s = m.settlement or {}
    if "accounts" in s:
        return list(s["accounts"]), s.get("default_id")
    if not m.payout_destination:
        return [], None
    legacy_id = str(uuid.uuid5(m.id, "legacy-payout-account"))
    details = {k: s.get(k, "") for k in DETAIL_KEYS}
    created = s.get("updated_at") or (m.created_at.isoformat() if m.created_at else None)
    return [{"id": legacy_id, "method": m.payout_method, "destination": m.payout_destination, "details": details,
             "created_at": created}], legacy_id


def _save(m: Merchant, accounts: list[dict], default_id: str | None) -> None:
    m.settlement = {"accounts": accounts, "default_id": default_id, "updated_at": datetime.now(UTC).isoformat()}
    default = next((a for a in accounts if a["id"] == default_id), None)
    m.payout_method = default["method"] if default else PayoutMethod.MPESA
    m.payout_destination = default["destination"] if default else ""


def add_account(m: Merchant, method: str, details: dict, make_default: bool) -> dict:
    accounts, default_id = accounts_of(m)
    if len(accounts) >= MAX_ACCOUNTS:
        raise ApiError(409, "too_many_accounts", f"You can add up to {MAX_ACCOUNTS} payout accounts. Remove one first.")
    d = {k: str(details.get(k, "") or "").strip() for k in DETAIL_KEYS}
    validate_details(method, d)
    destination = destination_for(method, d)
    if any(a["method"] == method and a["destination"] == destination for a in accounts):
        raise ApiError(409, "duplicate_account", "This account is already in your list.")
    account = {"id": str(uuid.uuid4()), "method": str(method), "destination": destination, "details": d,
               "created_at": datetime.now(UTC).isoformat()}
    accounts.append(account)
    _save(m, accounts, account["id"] if make_default or not default_id else default_id)
    return account


def remove_account(m: Merchant, account_id: str) -> dict:
    accounts, default_id = accounts_of(m)
    gone = next((a for a in accounts if a["id"] == account_id), None)
    if not gone:
        raise ApiError(404, "not_found", "Payout account not found.")
    accounts = [a for a in accounts if a["id"] != account_id]
    if default_id == account_id:
        default_id = accounts[0]["id"] if accounts else None
    _save(m, accounts, default_id)
    return gone


def set_default(m: Merchant, account_id: str) -> dict:
    accounts, _ = accounts_of(m)
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        raise ApiError(404, "not_found", "Payout account not found.")
    _save(m, accounts, account_id)
    return account

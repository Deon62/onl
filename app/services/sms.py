"""SMS alerts to merchants through Celcom Africa (https://isms.celcomafrica.com).

Alerts go to the merchant's own phones (set on the SMS page), never to their customers, so they know a payment
just landed. Without CELCOM_* settings, sends are skipped and reported as not configured.
"""

import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.models import Merchant

log = logging.getLogger("oryne.sms")

CELCOM_URL = "https://isms.celcomafrica.com/api/services/sendsms/"
MAX_RECIPIENTS = 3


@dataclass
class SmsResult:
    sent: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    error: str | None = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15)


def configured() -> bool:
    s = get_settings()
    return bool(s.celcom_api_key and s.celcom_partner_id and s.celcom_shortcode)


async def send_sms(recipients: list[str], message: str) -> SmsResult:
    """Send one message to up to a few numbers (2547XXXXXXXX). Never raises: the result says what happened."""
    s = get_settings()
    to = [r for r in dict.fromkeys(recipients) if r]
    if not to:
        return SmsResult(error="No recipient numbers.")
    if not configured():
        return SmsResult(failed=to, error="SMS is not set up yet (CELCOM_API_KEY, CELCOM_PARTNER_ID and CELCOM_SHORTCODE).")
    payload = {"apikey": s.celcom_api_key, "partnerID": s.celcom_partner_id, "shortcode": s.celcom_shortcode,
               "message": message, "mobile": ",".join(to)}
    try:
        async with _client() as http:
            res = await http.post(CELCOM_URL, json=payload)
        body = res.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Celcom unreachable: %s", e)
        return SmsResult(failed=to, error="Could not reach the SMS provider. Try again shortly.")

    result = SmsResult()
    rows = body.get("responses") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        log.warning("Celcom unexpected response %s: %s", res.status_code, str(body)[:300])
        return SmsResult(failed=to, error="The SMS provider rejected the request.")
    by_number = {str(r.get("mobile", "")): r for r in rows if isinstance(r, dict)}
    for number in to:
        row = by_number.get(number) or (rows[0] if len(rows) == 1 else {})
        code = row.get("response-code", row.get("respose-code"))
        if str(code) == "200":
            result.sent.append(number)
        else:
            result.failed.append(number)
            result.error = str(row.get("response-description") or "The SMS provider rejected the message.")
    if result.failed:
        log.warning("Celcom send failed for %s: %s", result.failed, result.error)
    return result


def payment_message(merchant_name: str, amount_cents: int, payer: str, receipt: str) -> str:
    who = f" from {payer}" if payer else ""
    return f"{merchant_name}: KES {amount_cents / 100:,.2f} received{who}. M-Pesa ref {receipt}. - Oryne"


async def notify_payment_received(merchant: Merchant, amount_cents: int, payer: str, receipt: str) -> SmsResult | None:
    """Alert the merchant's own phones about a confirmed payment. Called by the payments flow; no-op if alerts are off."""
    alerts = merchant.sms_alerts or {}
    recipients = (alerts.get("recipients") or [])[:MAX_RECIPIENTS]
    if not alerts.get("enabled") or not recipients:
        return None
    return await send_sms(recipients, payment_message(merchant.name, amount_cents, payer, receipt))

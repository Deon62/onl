import json

import httpx
import pytest

from app.config import get_settings
from app.models.enums import Role
from app.services import sms
from tests.conftest import add_merchant, add_profile, auth

EMPTY = {"phone": "", "till": "", "paybill": "", "paybill_account": "", "bank_name": "", "bank_branch": "",
         "account_name": "", "account_number": ""}


def acct(method, **details):
    return {"method": method, "details": EMPTY | details}


async def test_payout_accounts_list_default_and_remove(client, admin):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    h = auth(owner)

    r = await client.post("/v1/merchant/payout-accounts", headers=h, json=acct("M-Pesa", phone="0712 345 678"))
    assert r.status_code == 201, r.text
    m = r.json()
    assert len(m["payout_accounts"]) == 1 and m["payout_accounts"][0]["is_default"]
    assert m["payout_method"] == "M-Pesa" and m["payout_destination"] == "254712345678"

    m = (await client.post("/v1/merchant/payout-accounts", headers=h,
                           json=acct("Bank transfer", bank_name="Equity Bank", account_name="Acme Ltd", account_number="0123456789"))).json()
    assert [a["is_default"] for a in m["payout_accounts"]] == [True, False]
    assert m["payout_destination"] == "254712345678"  # first account stays default
    bank = m["payout_accounts"][1]
    assert bank["destination"] == "Equity Bank - A/C ****6789"

    # duplicates and bad details are rejected
    dup = await client.post("/v1/merchant/payout-accounts", headers=h, json=acct("M-Pesa", phone="254712345678"))
    assert dup.status_code == 409
    bad = await client.post("/v1/merchant/payout-accounts", headers=h, json=acct("Till", till="12"))
    assert bad.status_code == 422 and bad.json()["error"]["details"]["field"] == "till"

    m = (await client.post(f"/v1/merchant/payout-accounts/{bank['id']}/default", headers=h)).json()
    assert m["payout_method"] == "Bank transfer" and m["payout_accounts"][1]["is_default"]
    assert any(n["title"] == "Settlement account changed" for n in (await client.get("/v1/notifications", headers=auth(admin))).json())

    m = (await client.delete(f"/v1/merchant/payout-accounts/{bank['id']}", headers=h)).json()
    assert len(m["payout_accounts"]) == 1 and m["payout_accounts"][0]["is_default"] and m["payout_method"] == "M-Pesa"
    assert (await client.delete(f"/v1/merchant/payout-accounts/{bank['id']}", headers=h)).status_code == 404

    m = (await client.put("/v1/merchant/payout-schedule", headers=h, json={"payout_schedule": "Daily"})).json()
    assert m["payout_schedule"] == "Daily"


async def test_admin_manages_accounts_and_staff_cannot(client, admin):
    mid = await add_merchant()
    staff = await add_profile(Role.MERCHANT_STAFF, mid)
    body = acct("Paybill", paybill="247247", paybill_account="ACME01")
    assert (await client.post("/v1/merchant/payout-accounts", headers=auth(staff), json=body)).status_code == 403
    r = await client.post(f"/v1/merchant/payout-accounts?merchant_id={mid}", headers=auth(admin), json=body)
    assert r.status_code == 201 and r.json()["payout_destination"] == "Paybill 247247 · Acc ACME01"


async def test_legacy_single_account_is_listed(client):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    legacy = {"payout_method": "M-Pesa", "payout_destination": "254712345678", "payout_schedule": "Weekly",
              "settlement": EMPTY | {"phone": "0712345678"}}
    m = (await client.put("/v1/merchant/settlement", headers=auth(owner), json=legacy)).json()
    assert len(m["payout_accounts"]) == 1 and m["payout_accounts"][0]["destination"] == "254712345678"
    # adding a second keeps the legacy one in the list
    m = (await client.post("/v1/merchant/payout-accounts", headers=auth(owner), json=acct("Till", till="123456"))).json()
    assert [a["destination"] for a in m["payout_accounts"]] == ["254712345678", "Till 123456"]


@pytest.fixture
def celcom(monkeypatch):
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append(body)
        rows = [{"response-code": 200, "response-description": "Success", "mobile": n, "messageid": 1}
                for n in body["mobile"].split(",")]
        return httpx.Response(200, json={"responses": rows})

    monkeypatch.setattr(sms, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    s = get_settings()
    monkeypatch.setattr(s, "celcom_api_key", "k")
    monkeypatch.setattr(s, "celcom_partner_id", "1")
    monkeypatch.setattr(s, "celcom_shortcode", "ORYNE")
    return calls


async def test_sms_alerts_settings_and_test_send(client, celcom):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    h = auth(owner)
    assert (await client.post("/v1/merchant/sms-alerts/test", headers=h)).status_code == 422
    assert (await client.put("/v1/merchant/sms-alerts", headers=h, json={"enabled": True, "recipients": []})).status_code == 422
    assert (await client.put("/v1/merchant/sms-alerts", headers=h,
                             json={"enabled": True, "recipients": ["1", "2", "3", "4"]})).status_code == 422

    r = await client.put("/v1/merchant/sms-alerts", headers=h, json={"enabled": True, "recipients": ["0712 345 678", "0733000111"]})
    assert r.status_code == 200, r.text
    alerts = r.json()["sms_alerts"]
    assert alerts["enabled"] and alerts["recipients"] == ["254712345678", "254733000111"] and alerts["enabled_at"]

    t = (await client.post("/v1/merchant/sms-alerts/test", headers=h)).json()
    assert t == {"sent": ["254712345678", "254733000111"], "failed": [], "error": None}
    assert celcom[-1]["shortcode"] == "ORYNE" and celcom[-1]["mobile"] == "254712345678,254733000111"


async def test_notify_payment_received(celcom):
    class M:
        name = "Acme"
        sms_alerts = {"enabled": True, "recipients": ["254712345678"]}

    res = await sms.notify_payment_received(M(), 150000, "John", "QK12ABC")
    assert res.sent == ["254712345678"]
    assert celcom[-1]["message"] == "Acme: KES 1,500.00 received from John. M-Pesa ref QK12ABC. - Oryne"
    M.sms_alerts = {"enabled": False, "recipients": ["254712345678"]}
    assert await sms.notify_payment_received(M(), 100, "", "X") is None


async def test_sms_without_celcom_config_reports_it():
    res = await sms.send_sms(["254712345678"], "hi")
    assert res.sent == [] and "CELCOM_API_KEY" in res.error

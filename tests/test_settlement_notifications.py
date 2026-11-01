from app.models.enums import Role
from tests.conftest import add_merchant, add_profile, auth

BODY = {
    "payout_method": "M-Pesa", "payout_destination": "254712345678", "payout_schedule": "Weekly",
    "settlement": {"phone": "0712 345 678", "till": "", "paybill": "", "paybill_account": "", "bank_name": "",
                   "bank_branch": "", "account_name": "", "account_number": ""},
}


async def test_owner_updates_settlement_and_notifies(client, admin):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    r = await client.put("/v1/merchant/settlement", headers=auth(owner), json=BODY)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["payout_method"] == "M-Pesa" and m["payout_schedule"] == "Weekly"
    assert m["settlement"]["phone"] == "254712345678" and m["settlement"]["updated_at"]

    mine = (await client.get("/v1/notifications", headers=auth(owner))).json()
    assert [n["title"] for n in mine] == ["Settlement account updated"]
    everything = (await client.get("/v1/notifications", headers=auth(admin))).json()
    assert {n["audience"] for n in everything} == {"admin", str(mid)}

    assert (await client.post(f"/v1/notifications/read?audience={mid}", headers=auth(owner))).status_code == 204
    assert all(n["read"] for n in (await client.get("/v1/notifications", headers=auth(owner))).json())
    assert (await client.post("/v1/notifications/read?audience=admin", headers=auth(owner))).status_code == 404


async def test_staff_cannot_change_settlement(client):
    mid = await add_merchant()
    staff = await add_profile(Role.MERCHANT_STAFF, mid)
    assert (await client.put("/v1/merchant/settlement", headers=auth(staff), json=BODY)).status_code == 403


async def test_settlement_validation(client):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    bad = BODY | {"settlement": BODY["settlement"] | {"till": "12ab"}}
    assert (await client.put("/v1/merchant/settlement", headers=auth(owner), json=bad)).status_code == 422

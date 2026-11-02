from app.models.enums import Role
from tests.conftest import add_merchant, add_profile, auth

BODY = {"category": "Operational", "description": "Company registration", "amount_cents": 1065000,
        "provider": "eCitizen / BRS", "date": "2026-10-20", "status": "Paid"}


async def test_admin_records_edits_and_deletes_expense(client, admin):
    r = await client.post("/v1/admin/expenses", headers=auth(admin), json=BODY)
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["amount_cents"] == 1065000 and e["created_by"]

    listed = (await client.get("/v1/admin/expenses", headers=auth(admin))).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == e["id"]
    assert (await client.get("/v1/admin/expenses?from=2026-11-01", headers=auth(admin))).json()["total"] == 0

    r = await client.put(f"/v1/admin/expenses/{e['id']}", headers=auth(admin), json=BODY | {"status": "Pending"})
    assert r.status_code == 200 and r.json()["status"] == "Pending"

    assert (await client.delete(f"/v1/admin/expenses/{e['id']}", headers=auth(admin))).status_code == 204
    assert (await client.get("/v1/admin/expenses", headers=auth(admin))).json()["total"] == 0
    actions = [a["action"] for a in (await client.get("/v1/admin/activity", headers=auth(admin))).json()["items"]]
    assert {"Recorded expense", "Updated expense", "Deleted expense"} <= set(actions)


async def test_expense_permissions_and_validation(client, admin):
    ops = await add_profile(Role.OPS, email="ops@oryne.org")
    assert (await client.post("/v1/admin/expenses", headers=auth(ops), json=BODY)).status_code == 403
    assert (await client.get("/v1/admin/expenses", headers=auth(ops))).status_code == 200
    owner = await add_profile(Role.MERCHANT_OWNER, await add_merchant())
    assert (await client.get("/v1/admin/expenses", headers=auth(owner))).status_code == 403
    finance = await add_profile(Role.FINANCE, email="fin@oryne.org")
    assert (await client.post("/v1/admin/expenses", headers=auth(finance), json=BODY)).status_code == 201
    assert (await client.post("/v1/admin/expenses", headers=auth(admin), json=BODY | {"amount_cents": 0})).status_code == 422

from app.models.enums import Role
from tests.conftest import add_merchant, add_profile, auth

NEW = {
    "name": "Acme Car Hire",
    "email": "Accounts@AcmeCarHire.com",
    "phone": "0722 410 388",
    "contact_name": "Wanjiru Kamau",
    "domains": ["https://www.AcmeCarHire.com/book", "rent.acmecarhire.com"],
}


async def create(client, admin, body=None):
    return await client.post("/v1/admin/merchants", headers=auth(admin), json=body or NEW)


async def test_create_merchant_normalises_input(client, admin):
    r = await create(client, admin)
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["code"] == "ORY-M001"
    assert m["reference_prefix"] == "ACM"
    assert m["email"] == "accounts@acmecarhire.com"
    assert m["phone"] == "254722410388"
    assert m["status"] == "Pending Review"
    assert m["legal_name"] == "Acme Car Hire"
    assert sorted(d["domain"] for d in m["domains"]) == ["acmecarhire.com", "rent.acmecarhire.com"]
    assert m["pricing"] == {"percent_bps": 150, "fixed_cents": 0, "min_cents": 500, "max_cents": 150000}


async def test_codes_and_prefixes_are_unique(client, admin):
    await create(client, admin)
    r = await create(client, admin, {"name": "Acme Mart", "email": "hi@acmemart.co.ke"})
    assert r.status_code == 201
    assert r.json()["code"] == "ORY-M002"
    assert r.json()["reference_prefix"] != "ACM"


async def test_duplicate_email_and_domain_rejected(client, admin):
    await create(client, admin)
    r = await create(client, admin, {"name": "Other", "email": "accounts@acmecarhire.com"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    r = await create(client, admin, {"name": "Other", "email": "o@o.co.ke", "domains": ["acmecarhire.com"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "domain_taken"


async def test_validation_errors_are_readable(client, admin):
    r = await create(client, admin, {"name": "A", "email": "not-an-email", "phone": "12345"})
    assert r.status_code == 422
    fields = {f["field"] for f in r.json()["error"]["details"]["fields"]}
    assert {"name", "email", "phone"} <= fields


async def test_list_and_search(client, admin):
    await create(client, admin)
    await create(client, admin, {"name": "Nova Trading", "email": "finance@nova.co.ke", "domains": ["novatrading.co.ke"]})
    r = await client.get("/v1/admin/merchants", headers=auth(admin))
    assert r.json()["total"] == 2
    r = await client.get("/v1/admin/merchants?q=novatrading", headers=auth(admin))
    assert [m["name"] for m in r.json()["items"]] == ["Nova Trading"]
    r = await client.get("/v1/admin/merchants?status=Active", headers=auth(admin))
    assert r.json()["total"] == 0


async def test_update_pricing_and_status(client, admin):
    mid = (await create(client, admin)).json()["id"]
    r = await client.patch(f"/v1/admin/merchants/{mid}", headers=auth(admin),
                           json={"pricing": {"percent_bps": 120, "fixed_cents": 0, "min_cents": 1000, "max_cents": 200000}})
    assert r.status_code == 200
    assert r.json()["pricing"]["percent_bps"] == 120
    r = await client.post(f"/v1/admin/merchants/{mid}/status", headers=auth(admin), json={"status": "Active"})
    assert r.json()["status"] == "Active"
    log = (await client.get(f"/v1/admin/activity?merchant_id={mid}", headers=auth(admin))).json()
    actions = [a["action"] for a in log["items"]]
    assert "Activated merchant account" in actions and "Created merchant account" in actions


async def test_invalid_pricing_cap(client, admin):
    mid = (await create(client, admin)).json()["id"]
    r = await client.patch(f"/v1/admin/merchants/{mid}", headers=auth(admin),
                           json={"pricing": {"percent_bps": 150, "fixed_cents": 0, "min_cents": 5000, "max_cents": 100}})
    assert r.status_code == 422


async def test_domains_add_remove(client, admin):
    mid = (await create(client, admin)).json()["id"]
    r = await client.post(f"/v1/admin/merchants/{mid}/domains", headers=auth(admin), json={"domain": "HTTPS://shop.acme.co.ke/"})
    assert r.status_code == 201 and r.json()["domain"] == "shop.acme.co.ke"
    r = await client.delete(f"/v1/admin/merchants/{mid}/domains/{r.json()['id']}", headers=auth(admin))
    assert r.status_code == 204
    domains = (await client.get(f"/v1/admin/merchants/{mid}/domains", headers=auth(admin))).json()
    assert "shop.acme.co.ke" not in [d["domain"] for d in domains]


# --- Tenant isolation -------------------------------------------------------------

async def test_merchant_sees_only_own_account(client):
    acme = await add_merchant()
    nova = await add_merchant("Nova Trading", "ORY-M002", "NOV")
    owner = await add_profile(Role.MERCHANT_OWNER, acme)
    r = await client.get("/v1/merchant", headers=auth(owner))
    assert r.status_code == 200 and r.json()["code"] == "ORY-M001"
    r = await client.get(f"/v1/merchant?merchant_id={nova}", headers=auth(owner))
    assert r.status_code == 404


async def test_admin_views_as_merchant(client, admin):
    nova = await add_merchant("Nova Trading", "ORY-M002", "NOV")
    assert (await client.get("/v1/merchant", headers=auth(admin))).status_code == 400
    r = await client.get(f"/v1/merchant?merchant_id={nova}", headers=auth(admin))
    assert r.status_code == 200 and r.json()["name"] == "Nova Trading"


async def test_profile_update_owner_only(client):
    mid = await add_merchant()
    owner = await add_profile(Role.MERCHANT_OWNER, mid)
    staff = await add_profile(Role.MERCHANT_STAFF, mid)
    r = await client.patch("/v1/merchant/profile", headers=auth(owner), json={"industry": "Car rental", "phone": "+254 711 000 111"})
    assert r.status_code == 200
    assert r.json()["industry"] == "Car rental" and r.json()["phone"] == "254711000111"
    r = await client.patch("/v1/merchant/profile", headers=auth(staff), json={"industry": "Other"})
    assert r.status_code == 403

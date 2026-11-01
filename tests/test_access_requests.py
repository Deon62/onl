from tests.conftest import auth

REQ = {"business": "Kilele Foods", "contact_name": "Jane Doe", "email": "jane@kilele.co.ke",
       "phone": "0712345678", "volume": "KES 100,000 - 500,000", "message": "We sell online"}


async def test_submit_and_approve(client, admin):
    r = await client.post("/v1/access-requests", json=REQ)
    assert r.status_code == 202
    items = (await client.get("/v1/admin/access-requests", headers=auth(admin))).json()["items"]
    assert len(items) == 1 and items[0]["phone"] == "254712345678" and items[0]["status"] == "New"

    r = await client.post(f"/v1/admin/access-requests/{items[0]['id']}/approve", headers=auth(admin))
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Kilele Foods" and r.json()["status"] == "Pending Review"

    again = await client.post(f"/v1/admin/access-requests/{items[0]['id']}/approve", headers=auth(admin))
    assert again.status_code == 409


async def test_reject(client, admin):
    await client.post("/v1/access-requests", json=REQ)
    rid = (await client.get("/v1/admin/access-requests", headers=auth(admin))).json()["items"][0]["id"]
    r = await client.post(f"/v1/admin/access-requests/{rid}/reject", headers=auth(admin), json={"reason": "Unsupported business"})
    assert r.json()["status"] == "Rejected"


async def test_honeypot_is_dropped(client, admin):
    r = await client.post("/v1/access-requests", json=REQ | {"website": "http://spam"})
    assert r.status_code == 202
    assert (await client.get("/v1/admin/access-requests", headers=auth(admin))).json()["total"] == 0


async def test_rate_limited_per_email(client):
    for _ in range(3):
        assert (await client.post("/v1/access-requests", json=REQ)).status_code == 202
    r = await client.post("/v1/access-requests", json=REQ)
    assert r.status_code == 429


async def test_validation(client):
    r = await client.post("/v1/access-requests", json=REQ | {"phone": "999", "email": "nope"})
    assert r.status_code == 422

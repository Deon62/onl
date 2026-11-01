from sqlalchemy import select

from app.db import SessionLocal
from app.models import ApiKey
from app.models.enums import MerchantStatus
from app.security import hash_api_key
from tests.conftest import add_merchant, auth


async def new_key(client, admin, mid, kind="secret"):
    r = await client.post(f"/v1/admin/merchants/{mid}/api-keys", headers=auth(admin), json={"kind": kind, "label": "Website"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_key_shown_once_and_stored_hashed(client, admin):
    mid = await add_merchant()
    created = await new_key(client, admin, mid)
    raw = created["key"]
    assert raw.startswith("ory_sk_test_") and len(raw) == len("ory_sk_test_") + 40
    assert created["prefix"] == raw[:16]
    listed = (await client.get(f"/v1/admin/merchants/{mid}/api-keys", headers=auth(admin))).json()
    assert "key" not in listed[0]
    async with SessionLocal() as s:
        stored = (await s.execute(select(ApiKey))).scalar_one()
    assert stored.key_hash == hash_api_key(raw) and raw not in stored.key_hash


async def test_ping_with_secret_key(client, admin):
    mid = await add_merchant()
    raw = (await new_key(client, admin, mid))["key"]
    r = await client.get("/v1/ping", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200 and r.json()["merchant"] == "ORY-M001"
    r = await client.get("/v1/ping", headers={"X-Api-Key": raw})
    assert r.status_code == 200


async def test_invalid_and_revoked_keys(client, admin):
    mid = await add_merchant()
    created = await new_key(client, admin, mid)
    assert (await client.get("/v1/ping", headers={"X-Api-Key": "ory_sk_test_nope"})).status_code == 401
    assert (await client.get("/v1/ping", headers={"X-Api-Key": "random"})).status_code == 401
    await client.post(f"/v1/admin/merchants/{mid}/api-keys/{created['id']}/revoke", headers=auth(admin))
    r = await client.get("/v1/ping", headers={"X-Api-Key": created["key"]})
    assert r.status_code == 401


async def test_suspended_merchant_key_rejected(client, admin):
    mid = await add_merchant(status=MerchantStatus.SUSPENDED)
    raw = (await new_key(client, admin, mid))["key"]
    r = await client.get("/v1/ping", headers={"X-Api-Key": raw})
    assert r.status_code == 403 and r.json()["error"]["code"] == "merchant_inactive"


async def test_publishable_key_needs_registered_origin_and_cannot_use_secret_endpoints(client, admin):
    mid = await add_merchant()
    await client.post(f"/v1/admin/merchants/{mid}/domains", headers=auth(admin), json={"domain": "acmecarhire.com"})
    raw = (await new_key(client, admin, mid, "publishable"))["key"]
    assert raw.startswith("ory_pk_test_")
    r = await client.get("/v1/ping", headers={"X-Api-Key": raw, "Origin": "https://evil.example.com"})
    assert r.json()["error"]["code"] == "origin_not_allowed"
    r = await client.get("/v1/ping", headers={"X-Api-Key": raw, "Origin": "https://www.acmecarhire.com"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "secret_key_required"

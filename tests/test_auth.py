import uuid

from app.models.enums import Role
from tests.conftest import add_merchant, add_profile, auth, make_token


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


async def test_missing_token(client):
    r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


async def test_bad_signature(client, admin):
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {make_token(admin, secret='wrong-secret-wrong-secret-wrong-secret')}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


async def test_wrong_audience(client, admin):
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {make_token(admin, aud='anon')}"})
    assert r.status_code == 401


async def test_expired_token(client, admin):
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {make_token(admin, expires_in=-60)}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_expired"


async def test_valid_user_without_profile(client):
    r = await client.get("/v1/me", headers=auth(uuid.uuid4()))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "no_access"


async def test_me_admin(client, admin):
    r = await client.get("/v1/me", headers=auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "super_admin"
    assert body["merchant"] is None


async def test_me_merchant(client):
    mid = await add_merchant()
    uid = await add_profile(Role.MERCHANT_OWNER, mid)
    r = await client.get("/v1/me", headers=auth(uid))
    assert r.status_code == 200
    assert r.json()["merchant"]["code"] == "ORY-M001"


async def test_merchant_profile_without_merchant_is_rejected(client):
    uid = await add_profile(Role.MERCHANT_OWNER, None)
    r = await client.get("/v1/me", headers=auth(uid))
    assert r.status_code == 403


async def test_merchant_cannot_use_admin_routes(client):
    mid = await add_merchant()
    uid = await add_profile(Role.MERCHANT_OWNER, mid)
    r = await client.get("/v1/admin/merchants", headers=auth(uid))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_finance_can_read_but_not_create_merchants(client):
    uid = await add_profile(Role.FINANCE)
    assert (await client.get("/v1/admin/merchants", headers=auth(uid))).status_code == 200
    r = await client.post("/v1/admin/merchants", headers=auth(uid), json={"name": "X Ltd", "email": "x@x.co.ke"})
    assert r.status_code == 403

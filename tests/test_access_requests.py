import json
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Profile
from app.models.enums import Role
from app.services import email as email_service
from app.services import supabase_admin
from tests.conftest import add_merchant, add_profile, auth

REQ = {"business": "Kilele Foods", "contact_name": "Jane Doe", "email": "jane@kilele.co.ke", "phone": "0712345678",
       "domain": "https://www.KileleFoods.co.ke/shop", "volume": "KES 100,000 - 500,000", "message": "We sell online"}


def account(**over):
    """The merchant account an admin sets up from a request."""
    return {"merchant": {"name": "Kilele Foods", "legal_name": "Kilele Foods Ltd", "email": "jane@kilele.co.ke", "phone": "0712345678",
                         "contact_name": "Jane Doe", "industry": "Food", "location": "Nairobi", "status": "Active",
                         "domains": ["kilelefoods.co.ke"]} | over, "send_email": True}


class FakeSupabase:
    """Supabase Auth admin API double: records users and passwords."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append((request.method, request.url.path, body))
        assert request.headers["apikey"] == "sb_secret_test" and request.headers["authorization"] == "Bearer sb_secret_test"
        if request.method == "POST" and request.url.path.endswith("/admin/users"):
            if body["email"] in self.users:
                return httpx.Response(422, json={"code": 422, "error_code": "email_exists",
                                                 "msg": "A user with this email address has already been registered"})
            assert body["email_confirm"] is True
            self.users[body["email"]] = {"id": str(uuid.uuid4()), "email": body["email"], "password": body["password"]}
            return httpx.Response(200, json=self.users[body["email"]])
        if request.method == "GET" and request.url.path.endswith("/admin/users"):
            return httpx.Response(200, json={"users": list(self.users.values())})
        if request.method == "PUT":
            uid = request.url.path.rsplit("/", 1)[1]
            user = next(u for u in self.users.values() if u["id"] == uid)
            user["password"] = body["password"]
            return httpx.Response(200, json=user)
        return httpx.Response(404, json={"msg": "unexpected"})


@pytest.fixture
def supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(get_settings(), "supabase_url", "https://proj.supabase.co")
    monkeypatch.setattr(get_settings(), "supabase_secret_key", "sb_secret_test")
    real = supabase_admin._client

    def client():
        c = real()
        return httpx.AsyncClient(base_url=c.base_url, headers=c.headers, transport=httpx.MockTransport(fake.handler))
    monkeypatch.setattr(supabase_admin, "_client", client)
    return fake


@pytest.fixture
def resend(monkeypatch):
    sent: list[dict] = []
    status = {"code": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer re_test"
        sent.append(json.loads(request.content))
        return httpx.Response(status["code"], json={"id": "email_1"} if status["code"] < 300 else {"message": "Domain not verified"})
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")
    monkeypatch.setattr(email_service, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return sent, status


async def submit(client, **over):
    return await client.post("/v1/access-requests", json=REQ | over)


async def first_request(client, admin):
    return (await client.get("/v1/admin/access-requests", headers=auth(admin))).json()["items"][0]


# --- Public form -----------------------------------------------------------------

async def test_submit_requires_and_normalises_domain(client, admin):
    r = await client.post("/v1/access-requests", json={k: v for k, v in REQ.items() if k != "domain"})
    assert r.status_code == 422 and "domain" in {f["field"] for f in r.json()["error"]["details"]["fields"]}
    assert (await submit(client, domain="not a domain")).status_code == 422
    assert (await submit(client)).status_code == 202
    item = await first_request(client, admin)
    assert item["domain"] == "kilelefoods.co.ke" and item["phone"] == "254712345678" and item["status"] == "New"


async def test_honeypot_is_dropped(client, admin):
    assert (await submit(client, website="http://spam")).status_code == 202
    assert (await client.get("/v1/admin/access-requests", headers=auth(admin))).json()["total"] == 0


async def test_rate_limited_per_email(client):
    for _ in range(3):
        assert (await submit(client)).status_code == 202
    assert (await submit(client)).status_code == 429


# --- Approve: account + login + email ----------------------------------------------

async def test_approve_creates_merchant_login_and_emails(client, admin, supabase, resend):
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())
    assert r.status_code == 200, r.text
    body = r.json()
    m, login = body["merchant"], body["login"]
    assert m["code"] == "ORY-M001" and m["status"] == "Active" and m["domains"][0]["domain"] == "kilelefoods.co.ke"

    # Supabase user created with the returned password
    assert supabase.users["jane@kilele.co.ke"]["password"] == login["password"]
    assert len(login["password"]) == 14 and login["password"].count("-") == 2
    assert login["email"] == "jane@kilele.co.ke" and login["login_url"].endswith("/login")

    # Owner profile linked to the new merchant: the requester can sign in to their dashboard
    async with SessionLocal() as s:
        profile = (await s.execute(select(Profile).where(Profile.email == "jane@kilele.co.ke"))).scalar_one()
    assert profile.role == Role.MERCHANT_OWNER and str(profile.merchant_id) == m["id"]
    owner = {"Authorization": auth(profile.user_id)["Authorization"]}
    assert (await client.get("/v1/merchant", headers=owner)).json()["code"] == "ORY-M001"

    # Email via Resend with the password in both HTML and text parts
    sent, _ = resend
    assert login["email_sent"] is True and login["email_error"] is None
    assert sent[0]["to"] == ["jane@kilele.co.ke"] and "Welcome to Oryne" in sent[0]["subject"]
    assert login["password"] in sent[0]["html"] and login["password"] in sent[0]["text"] and "/login" in sent[0]["html"]

    assert (await first_request(client, admin))["status"] == "Approved"
    again = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())
    assert again.status_code == 409


async def test_approve_without_email_still_returns_password(client, admin, supabase):
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account() | {"send_email": False})
    login = r.json()["login"]
    assert r.status_code == 200 and login["email_sent"] is False and login["password"]


async def test_email_failure_is_reported_not_fatal(client, admin, supabase, resend):
    _, status = resend
    status["code"] = 403
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())
    login = r.json()["login"]
    assert r.status_code == 200 and login["email_sent"] is False and "Domain not verified" in login["email_error"]


async def test_email_not_configured(client, admin, supabase):
    await submit(client)
    req = await first_request(client, admin)
    login = (await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())).json()["login"]
    assert login["email_sent"] is False and "RESEND_API_KEY" in login["email_error"]


async def test_existing_supabase_user_gets_new_password(client, admin, supabase):
    supabase.users["jane@kilele.co.ke"] = {"id": str(uuid.uuid4()), "email": "jane@kilele.co.ke", "password": "old"}
    await submit(client)
    req = await first_request(client, admin)
    login = (await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())).json()["login"]
    assert supabase.users["jane@kilele.co.ke"]["password"] == login["password"] != "old"


async def test_login_email_used_by_admin_is_rejected(client, admin, supabase):
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account(email="admin@oryne.network"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "login_email_taken"
    assert (await first_request(client, admin))["status"] == "New"  # nothing half-created


async def test_secret_key_missing(client, admin):
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())
    assert r.status_code == 503 and r.json()["error"]["code"] == "auth_admin_not_configured"
    assert (await first_request(client, admin))["status"] == "New"


async def test_reject(client, admin):
    await submit(client)
    req = await first_request(client, admin)
    r = await client.post(f"/v1/admin/access-requests/{req['id']}/reject", headers=auth(admin), json={"reason": "Unsupported business"})
    assert r.json()["status"] == "Rejected"


# --- Re-issue login from the merchant page ------------------------------------------

async def test_send_login_resets_owner_password(client, admin, supabase, resend):
    await submit(client)
    req = await first_request(client, admin)
    first = (await client.post(f"/v1/admin/access-requests/{req['id']}/approve", headers=auth(admin), json=account())).json()
    r = await client.post(f"/v1/admin/merchants/{first['merchant']['id']}/login", headers=auth(admin), json={"send_email": True})
    assert r.status_code == 200
    login = r.json()
    assert login["password"] != first["login"]["password"]
    assert supabase.users["jane@kilele.co.ke"]["password"] == login["password"]
    sent, _ = resend
    assert "new Oryne password" in sent[-1]["subject"]


async def test_send_login_creates_owner_for_merchant_without_one(client, admin, supabase):
    mid = await add_merchant(email="owner@acme.co.ke")
    r = await client.post(f"/v1/admin/merchants/{mid}/login", headers=auth(admin), json={"send_email": False})
    assert r.status_code == 200 and r.json()["email"] == "owner@acme.co.ke"
    assert "owner@acme.co.ke" in supabase.users


async def test_finance_cannot_issue_logins(client, supabase):
    finance = await add_profile(Role.FINANCE)
    mid = await add_merchant()
    assert (await client.post(f"/v1/admin/merchants/{mid}/login", headers=auth(finance), json={})).status_code == 403


def test_password_shape():
    pw = supabase_admin.generate_password()
    assert len(pw) == 14 and not set(pw) & set("0O1lI")

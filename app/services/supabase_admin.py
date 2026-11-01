"""Supabase Auth admin: create merchant logins and set their passwords.

Uses the Auth admin REST API with the project's secret key (server-only).
"""

import secrets
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError

# No look-alike characters (0/O, 1/l/I), so a password read aloud or retyped from a screen still works.
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password() -> str:
    """Three groups of four, e.g. 'Kx7m-Qp4t-Hn9w' (~70 bits): strong, and easy to copy or type."""
    while True:
        groups = ["".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3)]
        pw = "-".join(groups)
        if any(c.isdigit() for c in pw) and any(c.isupper() for c in pw) and any(c.islower() for c in pw):
            return pw


def _client() -> httpx.AsyncClient:
    s = get_settings()
    if not (s.supabase_url and s.supabase_secret_key):
        raise ApiError(503, "auth_admin_not_configured",
                       "Creating logins needs SUPABASE_SECRET_KEY on the server (Supabase -> Project Settings -> API Keys -> Secret key).")
    key = s.supabase_secret_key
    return httpx.AsyncClient(
        base_url=s.supabase_url.rstrip("/") + "/auth/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )


def _error(res: httpx.Response) -> ApiError:
    try:
        body = res.json()
        msg = body.get("msg") or body.get("message") or body.get("error_description") or res.text
    except ValueError:
        msg = res.text
    return ApiError(502, "auth_admin_failed", f"Supabase could not update the login: {msg}")


async def _find_user_id(session: AsyncSession, http: httpx.AsyncClient, email: str) -> uuid.UUID | None:
    if session.bind.dialect.name == "postgresql":
        row = (await session.execute(text("SELECT id FROM auth.users WHERE lower(email) = lower(:e)"), {"e": email})).first()
        return uuid.UUID(str(row[0])) if row else None
    page = 1
    while True:  # fallback: scan the admin user list
        res = await http.get("/admin/users", params={"page": page, "per_page": 200})
        if res.status_code != 200:
            raise _error(res)
        users = res.json().get("users", [])
        for u in users:
            if (u.get("email") or "").lower() == email.lower():
                return uuid.UUID(u["id"])
        if len(users) < 200:
            return None
        page += 1


async def upsert_login(session: AsyncSession, email: str, password: str, full_name: str) -> uuid.UUID:
    """Create a confirmed Supabase user with this password, or reset the password if the user already exists."""
    async with _client() as http:
        res = await http.post("/admin/users", json={
            "email": email, "password": password, "email_confirm": True, "user_metadata": {"full_name": full_name},
        })
        if res.status_code in (200, 201):
            return uuid.UUID(res.json()["id"])
        if res.status_code not in (400, 409, 422):
            raise _error(res)
        user_id = await _find_user_id(session, http, email)
        if user_id is None:
            raise _error(res)
        upd = await http.put(f"/admin/users/{user_id}", json={"password": password, "email_confirm": True})
        if upd.status_code != 200:
            raise _error(upd)
        return user_id

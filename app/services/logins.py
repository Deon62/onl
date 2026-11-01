"""Merchant owner logins: create or reset the Supabase user, link the dashboard profile, email the details."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.models import Merchant, Profile
from app.models.enums import MERCHANT_ROLES, Role
from app.services.email import EmailResult, login_email, send_email
from app.services.supabase_admin import generate_password, upsert_login


async def issue_owner_login(session: AsyncSession, merchant: Merchant, *, email: str, name: str) -> str:
    """Give `email` owner access to `merchant` with a fresh password. Returns the password (shown once, never stored)."""
    email = email.strip().lower()
    existing = (await session.execute(select(Profile).where(func.lower(Profile.email) == email))).scalar_one_or_none()
    if existing and (existing.merchant_id != merchant.id or existing.role not in MERCHANT_ROLES):
        raise ApiError(409, "login_email_taken", f"{email} already signs in to another Oryne account. Use a different email.")

    password = generate_password()
    user_id: uuid.UUID = await upsert_login(session, email, password, name)

    profile = await session.get(Profile, user_id)
    if profile is None:
        session.add(Profile(user_id=user_id, email=email, full_name=name, role=Role.MERCHANT_OWNER, merchant_id=merchant.id))
    elif profile.merchant_id != merchant.id:
        raise ApiError(409, "login_email_taken", f"{email} already signs in to another Oryne account. Use a different email.")
    return password


async def owner_email(session: AsyncSession, merchant: Merchant) -> tuple[str, str]:
    """(email, name) of the merchant's first owner login, falling back to the business email and contact."""
    owner = (await session.execute(
        select(Profile).where(Profile.merchant_id == merchant.id, Profile.role == Role.MERCHANT_OWNER).order_by(Profile.created_at)
    )).scalars().first()
    if owner:
        return owner.email, owner.full_name or merchant.contact_name
    return merchant.email, merchant.contact_name


async def email_login(*, to: str, name: str, business: str, password: str, welcome: bool) -> EmailResult:
    login_url = get_settings().dashboard_url.rstrip("/") + "/login"
    subject, html, text = login_email(name=name, business=business, email=to, password=password, login_url=login_url, welcome=welcome)
    return await send_email(to, subject, html, text)

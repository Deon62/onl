"""Merchant creation and lookup rules."""

import re
import string
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Merchant, MerchantDomain
from app.schemas.merchant import MerchantCreate, Pricing

DEFAULT_PRICING = Pricing(percent_bps=150, fixed_cents=0, min_cents=500, max_cents=150_000)


async def next_merchant_code(session: AsyncSession) -> str:
    """ORY-M001, ORY-M002, ... (unique constraint protects against races; callers retry on conflict)."""
    codes = (await session.execute(select(Merchant.code))).scalars().all()
    nums = [int(m.group(1)) for c in codes if (m := re.fullmatch(r"ORY-M(\d+)", c))]
    return f"ORY-M{(max(nums) if nums else 0) + 1:03d}"


async def unique_reference_prefix(session: AsyncSession, name: str) -> str:
    """Three letters from the business name, unique across merchants (e.g. Acme Car Hire -> ACM)."""
    letters = re.sub(r"[^A-Za-z]", "", name).upper() or "MER"
    base = (letters + "XXX")[:3]
    taken = set((await session.execute(select(Merchant.reference_prefix))).scalars().all())
    candidates = [base] + [base[:2] + c for c in letters[2:] + string.ascii_uppercase]
    for c in candidates:
        if c not in taken:
            return c
    raise ApiError(409, "prefix_exhausted", "Could not allocate a payment reference prefix.")


async def get_merchant_or_404(session: AsyncSession, merchant_id: uuid.UUID) -> Merchant:
    m = await session.get(Merchant, merchant_id)
    if m is None:
        raise ApiError(404, "not_found", "Merchant not found.")
    return m


async def ensure_email_free(session: AsyncSession, email: str, exclude: uuid.UUID | None = None) -> None:
    q = select(func.count()).select_from(Merchant).where(func.lower(Merchant.email) == email.lower())
    if exclude:
        q = q.where(Merchant.id != exclude)
    if (await session.execute(q)).scalar_one():
        raise ApiError(409, "email_taken", "Another merchant already uses this email address.")


async def ensure_domains_free(session: AsyncSession, domains: list[str]) -> None:
    if not domains:
        return
    taken = (await session.execute(select(MerchantDomain.domain).where(MerchantDomain.domain.in_(domains)))).scalars().all()
    if taken:
        raise ApiError(409, "domain_taken", f"Already registered to another merchant: {', '.join(sorted(taken))}")


async def create_merchant(session: AsyncSession, data: MerchantCreate) -> Merchant:
    await ensure_email_free(session, data.email)
    domains = sorted(set(data.domains))
    await ensure_domains_free(session, domains)
    pricing = data.pricing or DEFAULT_PRICING
    merchant = Merchant(
        code=await next_merchant_code(session),
        name=data.name,
        legal_name=data.legal_name or data.name,
        email=data.email.lower(),
        phone=data.phone,
        contact_name=data.contact_name,
        industry=data.industry,
        location=data.location,
        status=data.status,
        reference_prefix=await unique_reference_prefix(session, data.name),
        pricing_percent_bps=pricing.percent_bps,
        pricing_fixed_cents=pricing.fixed_cents,
        pricing_min_cents=pricing.min_cents,
        pricing_max_cents=pricing.max_cents,
        payout_schedule=data.payout_schedule,
        payout_method=data.payout_method,
        payout_destination=data.payout_destination,
        subscription=data.subscription,
        settlement={},
        sms_alerts={"enabled": False, "recipients": [], "enabled_at": None},
        domains=[MerchantDomain(domain=d) for d in domains],
    )
    session.add(merchant)
    await session.flush()
    return merchant

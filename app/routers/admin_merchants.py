"""Admin: merchant accounts, their websites (domains) and API keys."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth import AdminUser, AdminWriter, Session
from app.errors import ApiError
from app.models import ApiKey, Merchant, MerchantDomain
from app.models.enums import MerchantStatus
from app.schemas.common import Page
from app.schemas.merchant import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    DomainCreate,
    DomainOut,
    MerchantCreate,
    MerchantOut,
    MerchantStatusUpdate,
    MerchantUpdate,
)
from app.security import generate_api_key
from app.services.audit import log_activity, notify
from app.services.merchants import create_merchant, ensure_domains_free, ensure_email_free, get_merchant_or_404

router = APIRouter(prefix="/v1/admin/merchants", tags=["admin: merchants"])


@router.get("", response_model=Page[MerchantOut])
async def list_merchants(
    _: AdminUser,
    session: Session,
    q: str | None = Query(None, max_length=100, description="Search name, code, email or domain"),
    status_: MerchantStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Merchant)
    if status_:
        query = query.where(Merchant.status == status_)
    if q:
        like = f"%{q.lower()}%"
        domain_match = select(MerchantDomain.merchant_id).where(MerchantDomain.domain.like(like))
        query = query.where(or_(
            func.lower(Merchant.name).like(like), func.lower(Merchant.code).like(like),
            func.lower(Merchant.email).like(like), Merchant.id.in_(domain_match),
        ))
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await session.execute(query.order_by(Merchant.created_at, Merchant.code).limit(limit).offset(offset))).scalars().all()
    return Page[MerchantOut](items=[MerchantOut.model_validate(m) for m in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=MerchantOut, status_code=status.HTTP_201_CREATED)
async def create(body: MerchantCreate, user: AdminWriter, session: Session, request: Request):
    for attempt in range(3):
        try:
            merchant = await create_merchant(session, body)
            log_activity(session, user=user, request=request, action="Created merchant account",
                         target=merchant.name, merchant_id=merchant.id)
            await session.commit()
            break
        except IntegrityError:
            # Two admins created merchants at the same moment and got the same code/prefix - retry.
            await session.rollback()
            if attempt == 2:
                raise ApiError(409, "conflict", "Could not create the merchant, please try again.") from None
    await session.refresh(merchant)
    return merchant


@router.get("/{merchant_id}", response_model=MerchantOut)
async def get_one(merchant_id: uuid.UUID, _: AdminUser, session: Session):
    return await get_merchant_or_404(session, merchant_id)


@router.patch("/{merchant_id}", response_model=MerchantOut)
async def update(merchant_id: uuid.UUID, body: MerchantUpdate, user: AdminWriter, session: Session, request: Request):
    merchant = await get_merchant_or_404(session, merchant_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in changes:
        changes["email"] = changes["email"].lower()
        await ensure_email_free(session, changes["email"], exclude=merchant.id)
    pricing = changes.pop("pricing", None)
    if pricing:
        # Applies to new payments only; fees already charged are never recalculated.
        merchant.pricing_percent_bps = pricing["percent_bps"]
        merchant.pricing_fixed_cents = pricing["fixed_cents"]
        merchant.pricing_min_cents = pricing["min_cents"]
        merchant.pricing_max_cents = pricing["max_cents"]
    for k, v in changes.items():
        setattr(merchant, k, v)
    log_activity(session, user=user, request=request, action="Edited merchant details", target=merchant.name, merchant_id=merchant.id)
    await session.commit()
    await session.refresh(merchant)
    return merchant


@router.post("/{merchant_id}/status", response_model=MerchantOut)
async def set_status(merchant_id: uuid.UUID, body: MerchantStatusUpdate, user: AdminWriter, session: Session, request: Request):
    merchant = await get_merchant_or_404(session, merchant_id)
    if merchant.status != body.status:
        merchant.status = body.status
        verb = {MerchantStatus.ACTIVE: "Activated", MerchantStatus.SUSPENDED: "Suspended"}.get(body.status, "Set to review")
        log_activity(session, user=user, request=request, action=f"{verb} merchant account",
                     target=f"{merchant.name}{' - ' + body.reason if body.reason else ''}", merchant_id=merchant.id)
        notify(session, merchant.id, f"Account {body.status.value.lower()}", f"Your Oryne account status is now {body.status.value}.")
        await session.commit()
        await session.refresh(merchant)
    return merchant


# --- Domains ---------------------------------------------------------------

@router.get("/{merchant_id}/domains", response_model=list[DomainOut])
async def list_domains(merchant_id: uuid.UUID, _: AdminUser, session: Session):
    return (await get_merchant_or_404(session, merchant_id)).domains


@router.post("/{merchant_id}/domains", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
async def add_domain(merchant_id: uuid.UUID, body: DomainCreate, user: AdminWriter, session: Session, request: Request):
    merchant = await get_merchant_or_404(session, merchant_id)
    await ensure_domains_free(session, [body.domain])
    domain = MerchantDomain(merchant_id=merchant.id, domain=body.domain)
    session.add(domain)
    log_activity(session, user=user, request=request, action=f"Added website {body.domain}", target=merchant.name, merchant_id=merchant.id)
    await session.commit()
    return domain


@router.delete("/{merchant_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(merchant_id: uuid.UUID, domain_id: uuid.UUID, user: AdminWriter, session: Session, request: Request):
    domain = await session.get(MerchantDomain, domain_id)
    if domain is None or domain.merchant_id != merchant_id:
        raise ApiError(404, "not_found", "Domain not found.")
    merchant = await get_merchant_or_404(session, merchant_id)
    log_activity(session, user=user, request=request, action=f"Removed website {domain.domain}", target=merchant.name, merchant_id=merchant_id)
    await session.delete(domain)
    await session.commit()


# --- API keys ---------------------------------------------------------------

@router.get("/{merchant_id}/api-keys", response_model=list[ApiKeyOut])
async def list_keys(merchant_id: uuid.UUID, _: AdminUser, session: Session):
    await get_merchant_or_404(session, merchant_id)
    q = select(ApiKey).where(ApiKey.merchant_id == merchant_id).order_by(ApiKey.created_at.desc())
    return (await session.execute(q)).scalars().all()


@router.post("/{merchant_id}/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(merchant_id: uuid.UUID, body: ApiKeyCreate, user: AdminWriter, session: Session, request: Request):
    """Creates a key for the merchant's website integration. The full key is returned only in this response."""
    merchant = await get_merchant_or_404(session, merchant_id)
    generated = generate_api_key(body.kind)
    key = ApiKey(merchant_id=merchant.id, kind=body.kind, label=body.label, prefix=generated.prefix,
                 key_hash=generated.hash, created_by=user.email)
    session.add(key)
    log_activity(session, user=user, request=request, action=f"Created {body.kind.value} API key {generated.prefix}...",
                 target=merchant.name, merchant_id=merchant.id)
    await session.commit()
    await session.refresh(key)
    return ApiKeyCreated(**ApiKeyOut.model_validate(key).model_dump(), key=generated.raw)


@router.post("/{merchant_id}/api-keys/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_key(merchant_id: uuid.UUID, key_id: uuid.UUID, user: AdminWriter, session: Session, request: Request):
    key = await session.get(ApiKey, key_id)
    if key is None or key.merchant_id != merchant_id:
        raise ApiError(404, "not_found", "API key not found.")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        merchant = await get_merchant_or_404(session, merchant_id)
        log_activity(session, user=user, request=request, action=f"Revoked API key {key.prefix}...", target=merchant.name, merchant_id=merchant_id)
        await session.commit()
        await session.refresh(key)
    return key

"""Access requests (public form + admin review), the activity log, and the integration ping."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select

from app.auth import AdminUser, AdminWriter, SecretClient, Session
from app.errors import ApiError
from app.models import AccessRequest, ActivityLog
from app.models.enums import AccessRequestStatus, MerchantStatus
from app.schemas.common import Message, Page
from app.schemas.merchant import MerchantCreate, MerchantOut
from app.schemas.platform import AccessRequestCreate, AccessRequestDecision, AccessRequestOut, ActivityOut
from app.services.audit import log_activity, notify
from app.services.merchants import create_merchant

router = APIRouter(prefix="/v1", tags=["platform"])

MAX_REQUESTS_PER_EMAIL_PER_DAY = 3


# --- Public: "Request access" on the sign-in page ---------------------------

@router.post("/access-requests", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def request_access(body: AccessRequestCreate, session: Session, request: Request):
    if body.website:  # honeypot filled -> silently accept and drop
        return Message(message="Request received.")
    since = datetime.now(UTC) - timedelta(days=1)
    recent = (await session.execute(
        select(func.count()).select_from(AccessRequest)
        .where(func.lower(AccessRequest.email) == body.email.lower(), AccessRequest.created_at >= since)
    )).scalar_one()
    if recent >= MAX_REQUESTS_PER_EMAIL_PER_DAY:
        raise ApiError(429, "too_many_requests", "We already have your request. Our team will be in touch.")
    req = AccessRequest(**body.model_dump(exclude={"website"}) | {"email": body.email.lower()})
    session.add(req)
    log_activity(session, actor=req.email, role="system", action="Requested merchant access", target=body.business, request=request)
    notify(session, "admin", "New access request", f"{body.business} ({body.contact_name}) - expected volume {body.volume}.")
    await session.commit()
    return Message(message="Request received. We will review it and contact you.")


# --- Admin: review access requests ------------------------------------------

@router.get("/admin/access-requests", response_model=Page[AccessRequestOut])
async def list_access_requests(
    _: AdminUser, session: Session,
    status_: AccessRequestStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    q = select(AccessRequest)
    if status_:
        q = q.where(AccessRequest.status == status_)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await session.execute(q.order_by(AccessRequest.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return Page[AccessRequestOut](items=[AccessRequestOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


async def _pending_request(session, request_id: uuid.UUID) -> AccessRequest:
    req = await session.get(AccessRequest, request_id)
    if req is None:
        raise ApiError(404, "not_found", "Access request not found.")
    if req.status != AccessRequestStatus.NEW:
        raise ApiError(409, "already_reviewed", f"This request was already {req.status.lower()}.")
    return req


@router.post("/admin/access-requests/{request_id}/approve", response_model=MerchantOut)
async def approve_access_request(request_id: uuid.UUID, user: AdminWriter, session: Session, request: Request):
    """Creates the merchant account (Pending Review until KYC is complete and it is activated)."""
    req = await _pending_request(session, request_id)
    merchant = await create_merchant(session, MerchantCreate(
        name=req.business, legal_name=req.business, email=req.email, phone=req.phone,
        contact_name=req.contact_name, status=MerchantStatus.PENDING_REVIEW,
    ))
    req.status = AccessRequestStatus.APPROVED
    req.merchant_id = merchant.id
    req.reviewed_by = user.email
    req.reviewed_at = datetime.now(UTC)
    log_activity(session, user=user, request=request, action="Approved access request", target=req.business, merchant_id=merchant.id)
    await session.commit()
    await session.refresh(merchant)
    return merchant


@router.post("/admin/access-requests/{request_id}/reject", response_model=AccessRequestOut)
async def reject_access_request(request_id: uuid.UUID, body: AccessRequestDecision, user: AdminWriter, session: Session, request: Request):
    req = await _pending_request(session, request_id)
    req.status = AccessRequestStatus.REJECTED
    req.reviewed_by = user.email
    req.reviewed_at = datetime.now(UTC)
    log_activity(session, user=user, request=request, action="Rejected access request",
                 target=f"{req.business}{' - ' + body.reason if body.reason else ''}")
    await session.commit()
    await session.refresh(req)
    return req


# --- Admin: activity log ------------------------------------------------------

@router.get("/admin/activity", response_model=Page[ActivityOut])
async def activity(
    _: AdminUser, session: Session,
    merchant_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    q = select(ActivityLog)
    if merchant_id:
        q = q.where(ActivityLog.merchant_id == merchant_id)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await session.execute(q.order_by(ActivityLog.at.desc()).limit(limit).offset(offset))).scalars().all()
    return Page[ActivityOut](items=[ActivityOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


# --- Client websites: verify an integration ------------------------------------

@router.get("/ping", tags=["payments API"])
async def ping(client: SecretClient):
    """Check that a merchant's secret API key works. Used when Oryne installs checkout on a client site."""
    return {"ok": True, "merchant": client.merchant.code, "name": client.merchant.name, "key": client.key.prefix}

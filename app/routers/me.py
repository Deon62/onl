"""The signed-in dashboard user, and the merchant's own business profile."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from sqlalchemy import select, update

from app.auth import MerchantUser, Session, User, scoped_merchant_id
from app.errors import ApiError
from app.models import Merchant, Notification
from app.models.enums import Role
from app.schemas.merchant import (
    MeOut,
    MerchantOut,
    MerchantProfileUpdate,
    PayoutAccountCreate,
    PayoutScheduleUpdate,
    SettlementUpdate,
    SmsAlertsUpdate,
    SmsTestOut,
)
from app.schemas.platform import NotificationOut
from app.services import payout_accounts, sms
from app.services.audit import log_activity, notify
from app.services.merchants import get_merchant_or_404

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me", response_model=MeOut)
async def me(user: User, session: Session):
    merchant = await session.get(Merchant, user.merchant_id) if user.merchant_id else None
    return MeOut(user_id=user.user_id, email=user.email, role=user.role,
                 merchant=MerchantOut.model_validate(merchant) if merchant else None)


@router.get("/merchant", response_model=MerchantOut)
async def my_merchant(user: MerchantUser, session: Session, merchant_id: uuid.UUID | None = None):
    """The merchant's own account. Admins pass ?merchant_id= to view as that merchant."""
    return await get_merchant_or_404(session, scoped_merchant_id(user, merchant_id))


@router.patch("/merchant/profile", response_model=MerchantOut)
async def update_my_profile(body: MerchantProfileUpdate, user: MerchantUser, session: Session, request: Request,
                            merchant_id: uuid.UUID | None = None):
    if user.role is Role.MERCHANT_STAFF or user.role is Role.FINANCE:
        raise ApiError(403, "forbidden", "Only the account owner can change the business profile.")
    merchant = await get_merchant_or_404(session, scoped_merchant_id(user, merchant_id))
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        setattr(merchant, k, v)
    if changes:
        log_activity(session, user=user, request=request, action="Updated business profile",
                     target=merchant.name, merchant_id=merchant.id)
    await session.commit()
    await session.refresh(merchant)
    return merchant


def _owner_only(user) -> None:
    if user.role is Role.MERCHANT_STAFF or user.role is Role.FINANCE:
        raise ApiError(403, "forbidden", "Only the account owner can change settlement details.")


@router.put("/merchant/settlement", response_model=MerchantOut)
async def update_settlement(body: SettlementUpdate, user: MerchantUser, session: Session, request: Request,
                            merchant_id: uuid.UUID | None = None):
    """Where the merchant's payouts are sent. A change of account notifies operations."""
    _owner_only(user)
    merchant = await get_merchant_or_404(session, scoped_merchant_id(user, merchant_id))
    changed = body.payout_method != merchant.payout_method or body.payout_destination != merchant.payout_destination
    merchant.payout_method = body.payout_method
    merchant.payout_destination = body.payout_destination
    merchant.payout_schedule = body.payout_schedule
    merchant.settlement = {**body.settlement.model_dump(), "updated_at": datetime.now(UTC).isoformat()}
    action = f"Changed settlement account to {body.payout_method}" if changed else "Updated payout schedule"
    log_activity(session, user=user, request=request, action=action, target=merchant.name, merchant_id=merchant.id)
    if changed:
        notify(session, "admin", "Settlement account changed", f"{merchant.name} now receives payouts by {body.payout_method}.")
        notify(session, merchant.id, "Settlement account updated", "New payouts will be sent to your updated account.")
    await session.commit()
    await session.refresh(merchant)
    return merchant


async def _owned(user, session, merchant_id):
    _owner_only(user)
    return await get_merchant_or_404(session, scoped_merchant_id(user, merchant_id))


async def _done(session, merchant):
    await session.commit()
    await session.refresh(merchant)
    return merchant


def _default_changed(session, merchant) -> None:
    notify(session, "admin", "Settlement account changed", f"{merchant.name} now receives payouts by {merchant.payout_method}.")


@router.post("/merchant/payout-accounts", response_model=MerchantOut, status_code=201)
async def add_payout_account(body: PayoutAccountCreate, user: MerchantUser, session: Session, request: Request,
                             merchant_id: uuid.UUID | None = None):
    """Add an account payouts can be sent to. The first account (or make_default) becomes the default."""
    merchant = await _owned(user, session, merchant_id)
    before = merchant.payout_destination
    account = payout_accounts.add_account(merchant, body.method, body.details.model_dump(), body.make_default)
    log_activity(session, user=user, request=request, action=f"Added {body.method} payout account",
                 target=account["destination"], merchant_id=merchant.id)
    if merchant.payout_destination != before:
        _default_changed(session, merchant)
    return await _done(session, merchant)


@router.post("/merchant/payout-accounts/{account_id}/default", response_model=MerchantOut)
async def default_payout_account(account_id: str, user: MerchantUser, session: Session, request: Request,
                                 merchant_id: uuid.UUID | None = None):
    merchant = await _owned(user, session, merchant_id)
    account = payout_accounts.set_default(merchant, account_id)
    log_activity(session, user=user, request=request, action="Changed default payout account",
                 target=account["destination"], merchant_id=merchant.id)
    _default_changed(session, merchant)
    return await _done(session, merchant)


@router.delete("/merchant/payout-accounts/{account_id}", response_model=MerchantOut)
async def delete_payout_account(account_id: str, user: MerchantUser, session: Session, request: Request,
                                merchant_id: uuid.UUID | None = None):
    merchant = await _owned(user, session, merchant_id)
    before = merchant.payout_destination
    gone = payout_accounts.remove_account(merchant, account_id)
    log_activity(session, user=user, request=request, action="Removed payout account",
                 target=gone["destination"], merchant_id=merchant.id)
    if merchant.payout_destination != before and merchant.payout_destination:
        _default_changed(session, merchant)
    return await _done(session, merchant)


@router.put("/merchant/payout-schedule", response_model=MerchantOut)
async def update_payout_schedule(body: PayoutScheduleUpdate, user: MerchantUser, session: Session, request: Request,
                                 merchant_id: uuid.UUID | None = None):
    merchant = await _owned(user, session, merchant_id)
    if merchant.payout_schedule != body.payout_schedule:
        merchant.payout_schedule = body.payout_schedule
        log_activity(session, user=user, request=request, action=f"Set payout schedule to {body.payout_schedule}",
                     target=merchant.name, merchant_id=merchant.id)
    return await _done(session, merchant)


@router.put("/merchant/sms-alerts", response_model=MerchantOut)
async def update_sms_alerts(body: SmsAlertsUpdate, user: MerchantUser, session: Session, request: Request,
                            merchant_id: uuid.UUID | None = None):
    """The merchant's own phones that get an SMS for every payment received (not their customers)."""
    merchant = await _owned(user, session, merchant_id)
    was = merchant.sms_alerts or {}
    enabled_at = (was.get("enabled_at") if was.get("enabled") else None) or datetime.now(UTC).isoformat()
    merchant.sms_alerts = {"enabled": body.enabled, "recipients": body.recipients, "enabled_at": enabled_at if body.enabled else None}
    if body.enabled and not was.get("enabled"):
        action = "Turned on SMS payment alerts"
    elif not body.enabled and was.get("enabled"):
        action = "Turned off SMS payment alerts"
    else:
        action = "Updated SMS alert numbers"
    log_activity(session, user=user, request=request, action=action, target=merchant.name, merchant_id=merchant.id)
    return await _done(session, merchant)


@router.post("/merchant/sms-alerts/test", response_model=SmsTestOut)
async def test_sms_alert(user: MerchantUser, session: Session, merchant_id: uuid.UUID | None = None):
    """Send a sample alert to the saved numbers so the merchant can check they arrive."""
    merchant = await _owned(user, session, merchant_id)
    recipients = (merchant.sms_alerts or {}).get("recipients") or []
    if not recipients:
        raise ApiError(422, "no_recipients", "Save at least one phone number first.")
    res = await sms.send_sms(recipients, f"{merchant.name}: SMS alerts are on. You will get a message like this for every payment received. - Oryne")
    return SmsTestOut(sent=res.sent, failed=res.failed, error=res.error)


@router.get("/notifications", response_model=list[NotificationOut])
async def notifications(user: User, session: Session, limit: int = Query(50, ge=1, le=200)):
    """Admins get platform and all merchant notifications (for view-as); merchant users only their own."""
    q = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if not user.is_admin:
        q = q.where(Notification.audience == str(user.merchant_id))
    return (await session.execute(q)).scalars().all()


@router.post("/notifications/read", status_code=204)
async def mark_read(user: User, session: Session, audience: str = Query(..., max_length=40)):
    if not user.is_admin and audience != str(user.merchant_id):
        raise ApiError(404, "not_found", "Not found.")
    await session.execute(update(Notification).where(Notification.audience == audience, ~Notification.read).values(read=True))
    await session.commit()

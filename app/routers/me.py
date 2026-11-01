"""The signed-in dashboard user, and the merchant's own business profile."""

import uuid

from fastapi import APIRouter, Request

from app.auth import MerchantUser, Session, User, scoped_merchant_id
from app.errors import ApiError
from app.models import Merchant
from app.models.enums import Role
from app.schemas.merchant import MeOut, MerchantOut, MerchantProfileUpdate
from app.services.audit import log_activity
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

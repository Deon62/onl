"""Merchant API schemas. All money fields are integer cents (KES x 100)."""

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.models.enums import ApiKeyKind, MerchantStatus, PayoutMethod, PayoutSchedule, Role
from app.schemas.common import Domain, KenyanPhone, Schema


class Pricing(Schema):
    percent_bps: int = Field(150, ge=0, le=1000, description="Percentage fee in basis points: 150 = 1.5%")
    fixed_cents: int = Field(0, ge=0)
    min_cents: int = Field(0, ge=0)
    max_cents: int = Field(0, ge=0, description="0 = no cap")

    @model_validator(mode="after")
    def _cap(self):
        if self.max_cents and self.max_cents < self.min_cents:
            raise ValueError("max_cents must be 0 (no cap) or at least min_cents")
        return self


class DomainOut(Schema):
    id: uuid.UUID
    domain: str
    verified_at: datetime | None
    created_at: datetime


class MerchantBase(Schema):
    name: str = Field(min_length=2, max_length=120)
    legal_name: str = Field("", max_length=200)
    email: EmailStr
    phone: KenyanPhone = ""
    contact_name: str = Field("", max_length=120)
    industry: str = Field("", max_length=80)
    location: str = Field("", max_length=120)
    subscription: str = Field("None", max_length=40)
    payout_schedule: PayoutSchedule = PayoutSchedule.MANUAL
    payout_method: PayoutMethod = PayoutMethod.MPESA
    payout_destination: str = Field("", max_length=120)


class MerchantCreate(MerchantBase):
    status: MerchantStatus = MerchantStatus.PENDING_REVIEW
    pricing: Pricing | None = None  # defaults to platform default pricing
    domains: list[Domain] = Field(default_factory=list, max_length=10)


class MerchantUpdate(Schema):
    """Admin edit. Omitted fields are left unchanged. Status changes use the /status endpoint."""

    name: str | None = Field(None, min_length=2, max_length=120)
    legal_name: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    phone: KenyanPhone | None = None
    contact_name: str | None = Field(None, max_length=120)
    industry: str | None = Field(None, max_length=80)
    location: str | None = Field(None, max_length=120)
    subscription: str | None = Field(None, max_length=40)
    payout_schedule: PayoutSchedule | None = None
    payout_method: PayoutMethod | None = None
    payout_destination: str | None = Field(None, max_length=120)
    pricing: Pricing | None = None


class MerchantProfileUpdate(Schema):
    """What a merchant may change about themselves (Business Profile page)."""

    contact_name: str | None = Field(None, max_length=120)
    phone: KenyanPhone | None = None
    industry: str | None = Field(None, max_length=80)
    location: str | None = Field(None, max_length=120)


class MerchantStatusUpdate(Schema):
    status: MerchantStatus
    reason: str = Field("", max_length=255)


class MerchantOut(Schema):
    id: uuid.UUID
    code: str
    name: str
    legal_name: str
    email: str
    phone: str
    contact_name: str
    industry: str
    location: str
    status: MerchantStatus
    reference_prefix: str
    pricing: Pricing
    payout_schedule: PayoutSchedule
    payout_method: PayoutMethod
    payout_destination: str
    settlement: dict
    sms_alerts: dict
    subscription: str
    domains: list[DomainOut]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_model(cls, data):
        # Build the nested pricing object from the flat ORM columns.
        if hasattr(data, "pricing_percent_bps"):
            return {
                **{k: getattr(data, k) for k in cls.model_fields if k != "pricing" and hasattr(data, k)},
                "pricing": Pricing(
                    percent_bps=data.pricing_percent_bps, fixed_cents=data.pricing_fixed_cents,
                    min_cents=data.pricing_min_cents, max_cents=data.pricing_max_cents,
                ),
            }
        return data


class DomainCreate(Schema):
    domain: Domain


class ApiKeyCreate(Schema):
    kind: ApiKeyKind = ApiKeyKind.SECRET
    label: str = Field("", max_length=80)


class ApiKeyOut(Schema):
    id: uuid.UUID
    kind: ApiKeyKind
    label: str
    prefix: str
    created_by: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="The full key. Shown only once - store it securely on the client's server.")


class MeOut(Schema):
    user_id: uuid.UUID
    email: str
    role: Role
    merchant: MerchantOut | None

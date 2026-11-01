"""Merchants (the businesses sharing Oryne's Till), their domains, API keys and dashboard users."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, created_at, one_of, updated_at, uuid_pk
from app.models.enums import ApiKeyKind, MerchantStatus, PayoutMethod, PayoutSchedule, Role


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = (
        one_of("status", MerchantStatus),
        one_of("payout_schedule", PayoutSchedule),
        one_of("payout_method", PayoutMethod),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Human-facing ID shown in the dashboard, e.g. ORY-M001
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    legal_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str] = mapped_column(String(16), default="")
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    industry: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default=MerchantStatus.PENDING_REVIEW)
    # 3-letter prefix used in payment references, e.g. ACM-7F3K2Q
    reference_prefix: Mapped[str] = mapped_column(String(3), unique=True)

    # Pricing: percentage in basis points (150 = 1.5%), amounts in cents. max 0 = no cap.
    pricing_percent_bps: Mapped[int] = mapped_column(Integer, default=150)
    pricing_fixed_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    pricing_min_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    pricing_max_cents: Mapped[int] = mapped_column(BigInteger, default=0)

    payout_schedule: Mapped[str] = mapped_column(String(10), default=PayoutSchedule.MANUAL)
    payout_method: Mapped[str] = mapped_column(String(20), default=PayoutMethod.MPESA)
    payout_destination: Mapped[str] = mapped_column(String(120), default="")
    settlement: Mapped[dict] = mapped_column(JSONType, default=dict)
    sms_alerts: Mapped[dict] = mapped_column(JSONType, default=lambda: {"enabled": False, "recipients": [], "enabled_at": None})
    subscription: Mapped[str] = mapped_column(String(40), default="None")

    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    domains: Mapped[list["MerchantDomain"]] = relationship(back_populates="merchant", cascade="all, delete-orphan", lazy="selectin")


class MerchantDomain(Base):
    """Websites allowed to start payments for a merchant (checked against the browser Origin)."""

    __tablename__ = "merchant_domains"

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()

    merchant: Mapped[Merchant] = relationship(back_populates="domains")


class ApiKey(Base):
    """Merchant API keys. Only a keyed hash is stored; the raw key is shown once at creation."""

    __tablename__ = "api_keys"
    __table_args__ = (one_of("kind", ApiKeyKind),)

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    label: Mapped[str] = mapped_column(String(80), default="")
    # First characters of the key, safe to display (e.g. "ory_sk_live_3f9a")
    prefix: Mapped[str] = mapped_column(String(24))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(254), default="")
    created_at: Mapped[datetime] = created_at()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Profile(Base):
    """Dashboard user. `user_id` is the Supabase Auth user id (auth.users.id)."""

    __tablename__ = "profiles"
    __table_args__ = (one_of("role", Role),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20))
    # Required for merchant roles, null for Oryne staff
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = created_at()

"""Oryne's own books and platform records: expenses, other revenue, access requests, audit log,
notifications and configuration."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, created_at, one_of, uuid_pk
from app.models.enums import AccessRequestStatus, ExpenseStatus


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (one_of("status", ExpenseStatus),)

    id: Mapped[uuid.UUID] = uuid_pk()
    category: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(120), default="")
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(10), default=ExpenseStatus.PAID)
    created_by: Mapped[str] = mapped_column(String(254), default="")
    created_at: Mapped[datetime] = created_at()


class RevenueEntry(Base):
    """Non-transactional income (e.g. subscriptions). Transaction, SMS and payout fees are derived from
    payments and payouts and are not duplicated here."""

    __tablename__ = "revenue_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = created_at()


class AccessRequest(Base):
    """'Request access' submissions from the sign-in page."""

    __tablename__ = "access_requests"
    __table_args__ = (one_of("status", AccessRequestStatus),)

    id: Mapped[uuid.UUID] = uuid_pk()
    business: Mapped[str] = mapped_column(String(120))
    contact_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(16))
    domain: Mapped[str] = mapped_column(String(253), default="", server_default="")
    volume: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default=AccessRequestStatus.NEW)
    documents: Mapped[list] = mapped_column(JSONType, default=list)  # Supabase Storage object paths
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"))
    reviewed_by: Mapped[str | None] = mapped_column(String(254))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


class ActivityLog(Base):
    __tablename__ = "activity_log"
    __table_args__ = (Index("ix_activity_merchant_at", "merchant_id", "at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    actor: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(255))
    target: Mapped[str] = mapped_column(String(255), default="")
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"))
    ip: Mapped[str | None] = mapped_column(String(45))
    at: Mapped[datetime] = created_at()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_audience_created", "audience", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    # "admin" or a merchant id (as text)
    audience: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at()


class PlatformConfig(Base):
    """Key/value platform settings (settlement hours, fees, provider costs)."""

    __tablename__ = "platform_config"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType)
    updated_by: Mapped[str] = mapped_column(String(254), default="system")
    updated_at: Mapped[datetime] = created_at()

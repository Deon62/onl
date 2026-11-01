"""Payouts to merchants and prepaid SMS credit."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, uuid_pk
from app.models.enums import InitiatedBy, PayoutMethod, PayoutStatus, Remittance


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (
        one_of("status", PayoutStatus),
        one_of("method", PayoutMethod),
        one_of("initiated_by", InitiatedBy),
        CheckConstraint(
            "remittance IS NULL OR remittance IN (" + ", ".join(f"'{r.value}'" for r in Remittance) + ")",
            name="remittance_valid",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="RESTRICT"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)          # debited from the merchant balance
    fee_cents: Mapped[int] = mapped_column(BigInteger, default=0)  # Oryne payout fee (revenue)
    net_cents: Mapped[int] = mapped_column(BigInteger)             # actually sent
    provider_cost_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    method: Mapped[str] = mapped_column(String(20))
    destination: Mapped[str] = mapped_column(String(120))  # snapshot of the settlement account at request time
    remittance: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default=PayoutStatus.PENDING)
    initiated_by: Mapped[str] = mapped_column(String(10))
    provider_ref: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(254))
    requested_at: Mapped[datetime] = created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SmsTopUp(Base):
    __tablename__ = "sms_topups"

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="RESTRICT"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(10))  # "M-Pesa" | "Balance"
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(20), unique=True)
    created_at: Mapped[datetime] = created_at()

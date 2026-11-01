"""Payments on the shared Till, raw Safaricom callbacks, and the merchant ledger."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, created_at, one_of, updated_at, uuid_pk
from app.models.enums import Attribution, CallbackKind, Channel, LedgerKind, PaymentStatus


class Payment(Base):
    """One customer payment attempt. Ownership (merchant_id) is fixed when the payment is initiated,
    before the customer pays - that is how money on the shared Till is separated per business."""

    __tablename__ = "payments"
    __table_args__ = (
        one_of("status", PaymentStatus),
        one_of("attribution", Attribution),
        one_of("channel", Channel),
        # A client site retrying the same order must not create a second STK push
        UniqueConstraint("merchant_id", "idempotency_key", name="uq_payments_merchant_idempotency"),
        Index("ix_payments_merchant_initiated", "merchant_id", "initiated_at"),
        Index("ix_payments_status_initiated", "status", "initiated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id", ondelete="RESTRICT"))
    reference: Mapped[str] = mapped_column(String(12), unique=True)  # Daraja AccountReference, max 12 chars
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    checkout_request_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    merchant_request_id: Mapped[str | None] = mapped_column(String(80))
    mpesa_receipt: Mapped[str | None] = mapped_column(String(20), unique=True)

    amount_cents: Mapped[int] = mapped_column(BigInteger)
    phone: Mapped[str] = mapped_column(String(16))  # 2547XXXXXXXX
    customer_name: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(String(120), default="")
    order_ref: Mapped[str] = mapped_column(String(80), default="")
    domain: Mapped[str | None] = mapped_column(String(253))
    channel: Mapped[str] = mapped_column(String(16), default=Channel.STK)
    status: Mapped[str] = mapped_column(String(12), default=PaymentStatus.INITIATED)
    attribution: Mapped[str] = mapped_column(String(10), default=Attribution.MATCHED)

    # Economics, fixed at confirmation time and never recalculated
    fee_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    provider_charge_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    sms_fee_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    sms_cost_cents: Mapped[int] = mapped_column(BigInteger, default=0)

    result_code: Mapped[int | None] = mapped_column(Integer)
    result_desc: Mapped[str | None] = mapped_column(String(255))
    initiated_at: Mapped[datetime] = created_at()
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = updated_at()


class Callback(Base):
    """Every request Safaricom sends is stored before it is processed (audit + safe replay)."""

    __tablename__ = "callbacks"
    __table_args__ = (one_of("kind", CallbackKind),)

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(20), index=True)
    payload: Mapped[dict] = mapped_column(JSONType)
    source_ip: Mapped[str | None] = mapped_column(String(45))
    received_at: Mapped[datetime] = created_at()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    error: Mapped[str | None] = mapped_column(Text)


class LedgerEntry(Base):
    """Append-only merchant ledger. Balances are sums of entries; rows are never updated or deleted.

    amount_cents is signed: credits to the merchant are positive, debits negative.
    available_at is when the entry counts toward the withdrawable balance (settlement window).
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        one_of("kind", LedgerKind),
        Index("ix_ledger_merchant_available", "merchant_id", "available_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(20))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    payout_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payouts.id", ondelete="RESTRICT"), index=True)
    sms_topup_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sms_topups.id", ondelete="RESTRICT"))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    memo: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[str] = mapped_column(String(254), default="system")
    created_at: Mapped[datetime] = created_at()

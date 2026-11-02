import uuid
from datetime import date, datetime

from pydantic import EmailStr, Field

from app.models.enums import AccessRequestStatus, ExpenseStatus, Role
from app.schemas.common import Domain, KenyanPhone, Schema
from app.schemas.merchant import MerchantCreate, MerchantOut


class AccessRequestCreate(Schema):
    business: str = Field(min_length=2, max_length=120)
    contact_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: KenyanPhone = Field(min_length=1)
    domain: Domain
    volume: str = Field(min_length=1, max_length=40)
    message: str = Field("", max_length=2000)
    # Honeypot: real users never fill this hidden field; bots usually do.
    website: str = Field("", max_length=200)


class AccessRequestOut(Schema):
    id: uuid.UUID
    business: str
    contact_name: str
    email: str
    phone: str
    domain: str
    volume: str
    message: str
    status: AccessRequestStatus
    documents: list
    merchant_id: uuid.UUID | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime


class AccessRequestDecision(Schema):
    reason: str = Field("", max_length=255)


class ActivityOut(Schema):
    id: uuid.UUID
    actor: str
    role: Role | str
    action: str
    target: str
    merchant_id: uuid.UUID | None
    at: datetime


class NotificationOut(Schema):
    id: uuid.UUID
    audience: str
    title: str
    body: str
    read: bool
    created_at: datetime


class LoginIssued(Schema):
    """A merchant owner's sign-in details. The password is returned once and never stored."""

    email: str
    password: str
    login_url: str
    email_sent: bool
    email_error: str | None = None


class ApproveAccessRequest(Schema):
    """The merchant account to create, pre-filled from the request and adjusted by the admin."""

    merchant: MerchantCreate
    send_email: bool = True


class ApprovedOut(Schema):
    merchant: MerchantOut
    login: LoginIssued


class SendLogin(Schema):
    send_email: bool = True


class ExpenseIn(Schema):
    """An Oryne operating cost. Amount is in cents (KES x 100)."""

    category: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=255)
    amount_cents: int = Field(gt=0, le=100_000_000_000)
    provider: str = Field("", max_length=120)
    date: date
    status: ExpenseStatus = ExpenseStatus.PAID


class ExpenseOut(ExpenseIn):
    id: uuid.UUID
    created_by: str
    created_at: datetime

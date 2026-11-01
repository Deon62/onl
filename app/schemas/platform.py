import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.models.enums import AccessRequestStatus, Role
from app.schemas.common import KenyanPhone, Schema


class AccessRequestCreate(Schema):
    business: str = Field(min_length=2, max_length=120)
    contact_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: KenyanPhone = Field(min_length=1)
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

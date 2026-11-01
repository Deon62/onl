"""Activity log and notifications. Callers add these in the same transaction as the change they describe."""

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.models import ActivityLog, Notification


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Render sits behind a proxy; the original client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def log_activity(
    session: AsyncSession,
    *,
    action: str,
    target: str = "",
    merchant_id: uuid.UUID | None = None,
    user: CurrentUser | None = None,
    actor: str | None = None,
    role: str | None = None,
    request: Request | None = None,
) -> None:
    session.add(ActivityLog(
        actor=actor or (user.email if user else "system"),
        role=role or (user.role.value if user else "system"),
        action=action,
        target=target,
        merchant_id=merchant_id,
        ip=client_ip(request),
    ))


def notify(session: AsyncSession, audience: str | uuid.UUID, title: str, body: str) -> None:
    session.add(Notification(audience=str(audience), title=title, body=body))

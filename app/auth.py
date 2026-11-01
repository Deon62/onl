"""Authentication and authorisation.

Dashboard users sign in with Supabase Auth; the dashboard sends the Supabase access token as
`Authorization: Bearer <jwt>`. We verify it, then load the user's `profiles` row, which holds their
role and (for merchant users) the one merchant they may see.

Client websites authenticate with a merchant API key: `Authorization: Bearer ory_sk_...`.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import ApiKey, Merchant, Profile
from app.models.enums import ADMIN_ROLES, ApiKeyKind, MerchantStatus, Role
from app.security import hash_api_key, kind_of

bearer = HTTPBearer(auto_error=False)
Session = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Supabase JWT verification
# ---------------------------------------------------------------------------

@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_supabase_token(token: str) -> dict:
    settings = get_settings()
    options = {"require": ["exp", "sub"]}
    try:
        if settings.supabase_jwt_secret:
            return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"],
                              audience=settings.supabase_jwt_audience, options=options)
        if settings.supabase_url:
            jwks_url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
            key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(token, key.key, algorithms=["ES256", "RS256"],
                              audience=settings.supabase_jwt_audience, options=options)
    except jwt.ExpiredSignatureError as e:
        raise ApiError(401, "token_expired", "Your session has expired. Please sign in again.") from e
    except (jwt.PyJWTError, ValueError) as e:
        raise ApiError(401, "invalid_token", "Invalid authentication token.") from e
    raise ApiError(500, "auth_not_configured", "Authentication is not configured on the server.")


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    email: str
    role: Role
    merchant_id: uuid.UUID | None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES


async def current_user(
    session: Session,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    if creds is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.")
    claims = verify_supabase_token(creds.credentials)
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as e:
        raise ApiError(401, "invalid_token", "Invalid authentication token.") from e
    profile = await session.get(Profile, user_id)
    if profile is None:
        raise ApiError(403, "no_access", "Your account has not been given access to Oryne yet.")
    role = Role(profile.role)
    if role not in ADMIN_ROLES and profile.merchant_id is None:
        raise ApiError(403, "no_access", "Your account is not linked to a business.")
    return CurrentUser(user_id=user_id, email=profile.email, role=role, merchant_id=profile.merchant_id)


User = Annotated[CurrentUser, Depends(current_user)]


def require_roles(*roles: Role):
    """Route dependency: allow only the given roles."""
    allowed = frozenset(roles)

    async def check(user: User) -> CurrentUser:
        if user.role not in allowed:
            raise ApiError(403, "forbidden", "You do not have permission to do this.")
        return user

    return check


AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN_ROLES))]
AdminWriter = Annotated[CurrentUser, Depends(require_roles(Role.SUPER_ADMIN, Role.OPS))]
SuperAdmin = Annotated[CurrentUser, Depends(require_roles(Role.SUPER_ADMIN))]


async def merchant_user(user: User) -> CurrentUser:
    """Merchant dashboard routes. Admins can use them too by passing ?merchant_id= (view as merchant)."""
    if user.merchant_id is None and not user.is_admin:
        raise ApiError(403, "forbidden", "This page is only for merchant accounts.")
    return user


MerchantUser = Annotated[CurrentUser, Depends(merchant_user)]


def scoped_merchant_id(user: CurrentUser, requested: uuid.UUID | None) -> uuid.UUID:
    """Tenant isolation: merchant users always get their own merchant; admins must name one."""
    if user.is_admin:
        if requested is None:
            raise ApiError(400, "merchant_required", "Pass merchant_id to view a merchant's data.")
        return requested
    assert user.merchant_id is not None
    if requested is not None and requested != user.merchant_id:
        raise ApiError(404, "not_found", "Merchant not found.")
    return user.merchant_id


# ---------------------------------------------------------------------------
# Merchant API keys (client websites)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApiClient:
    merchant: Merchant
    key: ApiKey
    kind: ApiKeyKind


async def api_client(
    request: Request,
    session: Session,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> ApiClient:
    raw = creds.credentials if creds else request.headers.get("x-api-key", "")
    kind = kind_of(raw)
    if not raw or kind is None:
        raise ApiError(401, "invalid_api_key", "Provide a valid Oryne API key.")
    key = (await session.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw)))).scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        raise ApiError(401, "invalid_api_key", "This API key is invalid or has been revoked.")
    merchant = await session.get(Merchant, key.merchant_id)
    if merchant is None or merchant.status != MerchantStatus.ACTIVE:
        raise ApiError(403, "merchant_inactive", "This merchant account is not active.")

    if kind is ApiKeyKind.PUBLISHABLE:
        # Browser keys only work from the merchant's own websites.
        origin = (request.headers.get("origin") or "").lower()
        host = origin.split("://", 1)[-1].split(":", 1)[0]
        allowed = {d.domain for d in merchant.domains}
        if not host or not any(host == d or host.endswith("." + d) for d in allowed):
            raise ApiError(403, "origin_not_allowed", "This website is not registered for this merchant.")

    key.last_used_at = datetime.now(UTC)
    await session.commit()
    return ApiClient(merchant=merchant, key=key, kind=kind)


Client = Annotated[ApiClient, Depends(api_client)]


async def secret_key_client(client: Client) -> ApiClient:
    if client.kind is not ApiKeyKind.SECRET:
        raise ApiError(403, "secret_key_required", "This endpoint requires a secret API key.")
    return client


SecretClient = Annotated[ApiClient, Depends(secret_key_client)]

"""Test setup: a throwaway SQLite database and real HS256 Supabase-style tokens."""

import os
import tempfile
import time
import uuid
from pathlib import Path

# Configure before the app is imported (settings and engine are created at import time).
_DB = Path(tempfile.gettempdir()) / f"oryne-test-{os.getpid()}.db"
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"sqlite+aiosqlite:///{_DB.as_posix()}",
    "SUPABASE_JWT_SECRET": "test-jwt-secret-that-is-long-enough-for-hs256",
    "API_KEY_PEPPER": "test-pepper",
})

import jwt  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Merchant, Profile  # noqa: E402
from app.models.enums import MerchantStatus, Role  # noqa: E402

JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]


def make_token(user_id: uuid.UUID, *, expires_in: int = 3600, secret: str = JWT_SECRET, aud: str = "authenticated") -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "aud": aud, "iat": now, "exp": now + expires_in, "role": "authenticated"},
                      secret, algorithm="HS256")


def auth(user_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def add_profile(role: Role, merchant_id: uuid.UUID | None = None, email: str | None = None) -> uuid.UUID:
    uid = uuid.uuid4()
    async with SessionLocal() as s:
        s.add(Profile(user_id=uid, email=email or f"{role.value}-{uid.hex[:6]}@test.ke", role=role, merchant_id=merchant_id))
        await s.commit()
    return uid


async def add_merchant(name: str = "Acme Car Hire", code: str = "ORY-M001", prefix: str = "ACM",
                       status: MerchantStatus = MerchantStatus.ACTIVE, email: str | None = None) -> uuid.UUID:
    async with SessionLocal() as s:
        m = Merchant(code=code, name=name, legal_name=name, email=email or f"{prefix.lower()}@test.ke",
                     reference_prefix=prefix, status=status, settlement={}, sms_alerts={})
        s.add(m)
        await s.commit()
        return m.id


@pytest.fixture
async def admin() -> uuid.UUID:
    return await add_profile(Role.SUPER_ADMIN, email="admin@oryne.network")

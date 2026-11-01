from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth import Session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: Session):
    """Render health check. Returns 503 if the database is unreachable."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "database": "ok"}

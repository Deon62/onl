"""Oryne API - payment collection for businesses sharing Oryne's M-Pesa Till."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import install_error_handlers
from app.routers import admin_merchants, expenses, health, me, platform

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("oryne")

ROOT = Path(__file__).resolve().parents[1]


def run_migrations() -> None:
    """alembic upgrade head. Runs at startup in production so schema changes ship with each deploy,
    whether or not the host runs a pre-deploy command."""
    from alembic.config import Config

    from alembic import command

    cfg = Config()  # no ini file: keeps the app's logging configuration intact
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().environment == "production":
        await asyncio.to_thread(run_migrations)  # alembic's env.py runs its own event loop
        log.info("Database schema is up to date")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_production()

    app = FastAPI(
        title="Oryne API",
        version="0.1.0",
        description="Payment collection for businesses sharing Oryne's M-Pesa Till. All amounts are in cents (KES x 100).",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)

    # Unexpected errors become a JSON 500 *inside* the CORS middleware, so browsers see the real error
    # instead of a misleading "blocked by CORS policy". (Registered first = runs inside CORS.)
    @app.middleware("http")
    async def catch_unhandled(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            log.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse({"error": {"code": "internal_error", "message": "Something went wrong on our side."}}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Api-Key", "Idempotency-Key"],
    )
    for r in (health.router, me.router, admin_merchants.router, platform.router, expenses.router):
        app.include_router(r)
    return app


app = create_app()

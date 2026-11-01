"""Oryne API - payment collection for businesses sharing Oryne's M-Pesa Till."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.routers import admin_merchants, health, me, platform

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_production()

    app = FastAPI(
        title="Oryne API",
        version="0.1.0",
        description="Payment collection for businesses sharing Oryne's M-Pesa Till. All amounts are in cents (KES x 100).",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Api-Key", "Idempotency-Key"],
    )
    for r in (health.router, me.router, admin_merchants.router, platform.router):
        app.include_router(r)
    return app


app = create_app()

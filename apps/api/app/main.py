from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import CSRFMiddleware, InMemoryRateLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.monitoring import configure_error_monitoring
from app.db.session import check_database, init_db
from app.routers import admin, analysis, audit_logs, auth, cases, documents, gazette, payments, pricing, reports, reviews, uploads
from app.schemas import HealthResponse

configure_logging()
configure_error_monitoring()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield

app = FastAPI(
    title="Mradi wa Ardhi API",
    version="0.1.0",
    description="Land transaction due-diligence API with AI-assisted risk analysis.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "accept",
        "authorization",
        "content-type",
        "x-csrf-token",
        "x-request-id",
        "x-dev-role",
    ],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(ok=True, service="mradi-api", environment=settings.app_env, checks={"application": "ok"})


@app.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    try:
        check_database()
    except Exception:
        logger.exception("health.ready.failed", check="database")
        raise HTTPException(status_code=503, detail={"ok": False, "checks": {"database": "failed"}}) from None
    return HealthResponse(ok=True, service="mradi-api", environment=settings.app_env, checks={"database": "ok"})


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return await healthz()


app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(uploads.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(analysis.api_router)
app.include_router(gazette.router)
app.include_router(reports.router)
app.include_router(reviews.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(audit_logs.router)
app.include_router(pricing.router)

if settings.otel_exporter_otlp_endpoint:
    FastAPIInstrumentor.instrument_app(app)

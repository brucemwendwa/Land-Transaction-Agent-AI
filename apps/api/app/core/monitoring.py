from __future__ import annotations

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


def configure_error_monitoring() -> None:
    if not settings.sentry_dsn:
        logger.info("error_monitoring.disabled", provider="sentry")
        return

    try:
        import sentry_sdk
    except Exception:
        logger.warning("error_monitoring.unavailable", provider="sentry")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        send_default_pii=False,
    )
    logger.info("error_monitoring.enabled", provider="sentry")

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Notification


def queue_email_notification(
    db: Session,
    *,
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    organization_id: str | None = None,
    case_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Notification:
    """Persist an email notification intent without pretending delivery occurred."""
    notification = Notification(
        user_id=user_id,
        organization_id=organization_id,
        case_id=case_id,
        notification_type=notification_type,
        title=title,
        body=body,
        channel="email",
        status="queued",
        metadata_json={
            **(metadata or {}),
            "delivery_status": "not_configured",
            "delivery_note": "No email provider is configured in this build.",
        },
    )
    db.add(notification)
    db.flush()
    return notification

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, TimelineEvent, User

_SENSITIVE_METADATA_KEYS = {
    "ai_value",
    "content",
    "corrected_value",
    "email",
    "filename",
    "full_name",
    "id_number",
    "kra_pin",
    "phone",
    "quote",
    "raw_payload",
    "raw_text",
    "reviewer_email",
    "text_snippet",
    "value",
}


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str,
    actor: User | None = None,
    request: Request | None = None,
    case_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    ip = ""
    if request is not None and request.client is not None:
        ip = request.headers.get("x-forwarded-for", request.client.host)
    log = AuditLog(
        actor_user_id=actor.id if actor else None,
        organization_id=actor.organization_id if actor else None,
        case_id=case_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip,
        metadata_json=_sanitize_metadata(metadata or {}),
    )
    db.add(log)
    db.flush()
    return log


def write_timeline(
    db: Session,
    *,
    case_id: str,
    event_type: str,
    title: str,
    actor: User | None = None,
    metadata: dict[str, Any] | None = None,
) -> TimelineEvent:
    event = TimelineEvent(
        case_id=case_id,
        actor_user_id=actor.id if actor else None,
        event_type=event_type,
        title=title,
        metadata_json=metadata or {},
    )
    db.add(event)
    db.flush()
    return event


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            sanitized[key_text] = "[redacted]" if key_text.lower() in _SENSITIVE_METADATA_KEYS else _sanitize_metadata(item)
        return sanitized
    return value

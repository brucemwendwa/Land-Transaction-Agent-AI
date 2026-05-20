from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, require_roles
from app.domain.enums import UserRole
from app.models import AuditLog, User
from app.schemas import AuditLogRead
from app.services.audit import write_audit

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AuditLog]:
    if current_user.role == UserRole.ADMIN:
        write_audit(
            db,
            action="admin.audit_logs.list",
            target_type="admin",
            target_id="audit_logs",
            actor=current_user,
            request=request,
        )
        db.commit()
    query = db.query(AuditLog)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(AuditLog.actor_user_id == current_user.id)
    return query.order_by(AuditLog.created_at.desc()).limit(200).all()


@router.get("/admin", response_model=list[AuditLogRead])
async def admin_audit_logs(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[AuditLog]:
    write_audit(
        db,
        action="admin.audit_logs.list",
        target_type="admin",
        target_id="audit_logs",
        actor=current_user,
        request=request,
    )
    db.commit()
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()

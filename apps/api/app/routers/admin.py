from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import require_roles
from app.domain.enums import UserRole
from app.models import Document, LandCase, User, VerificationAttempt
from app.schemas import CaseRead, UserRead
from app.services.audit import write_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
async def admin_users(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[User]:
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    write_audit(
        db,
        action="admin.users.list",
        target_type="admin",
        target_id="users",
        actor=current_user,
        request=request,
        metadata={"result_count": len(users)},
    )
    db.commit()
    return users


@router.get("/cases", response_model=list[CaseRead])
async def admin_cases(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[LandCase]:
    cases = (
        db.query(LandCase)
        .options(selectinload(LandCase.documents).selectinload(Document.extracted_fields))
        .order_by(LandCase.updated_at.desc())
        .limit(200)
        .all()
    )
    write_audit(
        db,
        action="admin.cases.list",
        target_type="admin",
        target_id="cases",
        actor=current_user,
        request=request,
        metadata={"result_count": len(cases)},
    )
    db.commit()
    return cases


@router.get("/verification-attempts")
async def verification_attempts(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> list[dict[str, str]]:
    attempts = db.query(VerificationAttempt).order_by(VerificationAttempt.created_at.desc()).limit(200).all()
    write_audit(
        db,
        action="admin.verification_attempts.list",
        target_type="admin",
        target_id="verification_attempts",
        actor=current_user,
        request=request,
        metadata={"result_count": len(attempts)},
    )
    db.commit()
    return [
        {
            "id": attempt.id,
            "case_id": attempt.case_id,
            "adapter_name": attempt.adapter_name,
            "status": attempt.status.value,
            "message": attempt.message,
        }
        for attempt in attempts
    ]

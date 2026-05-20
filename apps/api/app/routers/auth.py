from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import UserRead
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
async def read_me(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    write_audit(
        db,
        action="auth.login",
        target_type="user",
        target_id=current_user.id,
        actor=current_user,
        request=request,
    )
    db.commit()
    return current_user

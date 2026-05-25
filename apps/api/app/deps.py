from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import local_dev_principal, verify_clerk_jwt
from app.db.session import get_db
from app.domain.enums import UserRole
from app.models import LandCase, User


async def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if settings.auth_bypass_enabled:
        principal = local_dev_principal()
        dev_role = request.headers.get("x-dev-role")
        if dev_role:
            principal.role = dev_role
    else:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        principal = await verify_clerk_jwt(authorization.split(" ", 1)[1])

    valid_roles = {role.value for role in UserRole}
    role = UserRole(principal.role) if principal.role in valid_roles else UserRole.BUYER
    user = db.query(User).filter(User.clerk_user_id == principal.subject).one_or_none()
    if user is None:
        user = User(
            clerk_user_id=principal.subject,
            email=principal.email,
            full_name=principal.full_name,
            role=role,
        )
        db.add(user)
    else:
        user.email = principal.email
        user.full_name = principal.full_name or user.full_name
        user.role = role
    db.commit()
    db.refresh(user)
    return user


def require_roles(*roles: UserRole) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency


def get_case_for_user(case_id: str, db: Session, current_user: User) -> LandCase:
    case = db.query(LandCase).filter(LandCase.id == case_id).one_or_none()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if current_user.role != UserRole.ADMIN and case.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case is not accessible")
    return case

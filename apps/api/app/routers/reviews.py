from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.models import ReviewRequest, User
from app.schemas import ReviewRequestCreate, ReviewRequestRead
from app.services.audit import write_audit, write_timeline

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewRequestRead])
async def list_review_requests(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ReviewRequest]:
    query = db.query(ReviewRequest)
    if current_user.role.value != "admin":
        query = query.filter(
            or_(
                ReviewRequest.requested_by_user_id == current_user.id,
                ReviewRequest.reviewer_email == current_user.email,
            )
        )
    return query.order_by(ReviewRequest.created_at.desc()).all()


@router.post("", response_model=ReviewRequestRead, status_code=201)
async def create_review_request(
    payload: ReviewRequestCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewRequest:
    case = get_case_for_user(payload.case_id, db, current_user)
    review = ReviewRequest(
        case_id=case.id,
        requested_by_user_id=current_user.id,
        reviewer_role=payload.reviewer_role,
        reviewer_email=str(payload.reviewer_email),
        note=payload.note,
    )
    db.add(review)
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="review_requested",
        title=f"{payload.reviewer_role.value.title()} review requested",
        metadata={"reviewer_email": str(payload.reviewer_email)},
    )
    write_audit(
        db,
        action="review.request.create",
        target_type="review_request",
        target_id=review.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
    db.refresh(review)
    return review

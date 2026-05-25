from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user, require_roles
from app.domain.enums import UserRole
from app.models import ReviewRequest, User
from app.schemas import ReviewAssignRequest, ReviewRequestCreate, ReviewRequestRead, ReviewUpdateRequest
from app.services.audit import write_audit, write_timeline
from app.services.notifications import queue_email_notification

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
                ReviewRequest.assigned_to_user_id == current_user.id,
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
    queue_email_notification(
        db,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        case_id=case.id,
        notification_type="expert_review_requested",
        title=f"{payload.reviewer_role.value.title()} review requested",
        body="An expert review request was created. Email delivery is queued when a mail provider is configured.",
        metadata={"reviewer_role": payload.reviewer_role.value, "review_id": review.id},
    )
    db.commit()
    db.refresh(review)
    return review


@router.get("/assigned", response_model=list[ReviewRequestRead])
async def assigned_reviews(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADVOCATE, UserRole.SURVEYOR, UserRole.ADMIN))],
) -> list[ReviewRequest]:
    query = db.query(ReviewRequest)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(
            or_(
                ReviewRequest.assigned_to_user_id == current_user.id,
                ReviewRequest.reviewer_email == current_user.email,
            )
        )
    return query.order_by(ReviewRequest.created_at.desc()).all()


@router.post("/{review_id}/assign", response_model=ReviewRequestRead)
async def assign_review(
    review_id: str,
    payload: ReviewAssignRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> ReviewRequest:
    review = db.query(ReviewRequest).filter(ReviewRequest.id == review_id).one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review request not found")
    expert = db.query(User).filter(User.id == payload.assigned_to_user_id).one_or_none()
    if expert is None:
        raise HTTPException(status_code=404, detail="Assigned expert not found")
    review.assigned_to_user_id = expert.id
    review.reviewer_email = str(payload.reviewer_email or expert.email)
    review.status = "assigned"
    review.metadata_json = {
        **(review.metadata_json or {}),
        "assigned_by_user_id": current_user.id,
        "email_notification": "queued",
    }
    write_timeline(
        db,
        case_id=review.case_id,
        actor=current_user,
        event_type="review_assigned",
        title=f"{review.reviewer_role.value.title()} review assigned",
        metadata={"review_id": review.id, "assigned_to_user_id": expert.id},
    )
    write_audit(
        db,
        action="review.assign",
        target_type="review_request",
        target_id=review.id,
        actor=current_user,
        request=request,
        case_id=review.case_id,
    )
    queue_email_notification(
        db,
        user_id=expert.id,
        organization_id=expert.organization_id,
        case_id=review.case_id,
        notification_type="expert_review_assigned",
        title="Expert review assigned",
        body="A land transaction review has been assigned to you.",
        metadata={"review_id": review.id, "assigned_by_user_id": current_user.id},
    )
    db.commit()
    db.refresh(review)
    return review


@router.patch("/{review_id}", response_model=ReviewRequestRead)
async def update_review(
    review_id: str,
    payload: ReviewUpdateRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewRequest:
    review = db.query(ReviewRequest).filter(ReviewRequest.id == review_id).one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review request not found")
    can_update = (
        current_user.role == UserRole.ADMIN
        or review.assigned_to_user_id == current_user.id
        or review.reviewer_email == current_user.email
    )
    if not can_update:
        raise HTTPException(status_code=403, detail="Review request is not accessible")
    changes = payload.model_dump(exclude_unset=True)
    if payload.status is not None:
        review.status = payload.status
        if payload.status == "completed":
            review.completed_at = datetime.now(UTC).replace(tzinfo=None)
    if payload.review_summary is not None:
        review.review_summary = payload.review_summary
    if payload.recommendation is not None:
        review.recommendation = payload.recommendation
    if payload.attachment_document_ids:
        review.metadata_json = {
            **(review.metadata_json or {}),
            "attachment_document_ids": payload.attachment_document_ids,
        }
    write_timeline(
        db,
        case_id=review.case_id,
        actor=current_user,
        event_type="review_updated",
        title=f"Review updated: {review.status}",
        metadata={"review_id": review.id, "changes": sorted(changes)},
    )
    write_audit(
        db,
        action="review.update",
        target_type="review_request",
        target_id=review.id,
        actor=current_user,
        request=request,
        case_id=review.case_id,
        metadata={"status": review.status},
    )
    queue_email_notification(
        db,
        user_id=review.requested_by_user_id,
        organization_id=current_user.organization_id,
        case_id=review.case_id,
        notification_type="expert_review_updated",
        title=f"Expert review {review.status.replace('_', ' ')}",
        body="An expert review status or recommendation was updated.",
        metadata={"review_id": review.id, "status": review.status},
    )
    db.commit()
    db.refresh(review)
    return review

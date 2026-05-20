from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.domain.enums import CaseStatus, UserRole
from app.models import (
    AuditLog,
    Document,
    GazetteSearch,
    GazetteSearchResult,
    LandCase,
    Report,
    RiskAnalysisResult,
    TimelineEvent,
    User,
    VerificationAttempt,
)
from app.schemas import (
    CaseAgentAnswerResponse,
    CaseAgentQuestionRequest,
    CaseCreate,
    CaseRead,
    CaseUpdate,
    DeleteCaseResponse,
    TimelineEventRead,
)
from app.services.audit import write_audit, write_timeline
from app.services.case_agent import answer_case_question
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseRead])
async def list_cases(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[LandCase]:
    query = db.query(LandCase).options(
        selectinload(LandCase.documents).selectinload(Document.extracted_fields),
        selectinload(LandCase.documents).selectinload(Document.field_corrections),
    )
    if current_user.role != UserRole.ADMIN:
        query = query.filter(LandCase.owner_user_id == current_user.id)
    return query.order_by(LandCase.updated_at.desc()).all()


@router.post("", response_model=CaseRead, status_code=201)
async def create_case(
    payload: CaseCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LandCase:
    case = LandCase(owner_user_id=current_user.id, organization_id=current_user.organization_id, **payload.model_dump())
    db.add(case)
    db.flush()
    write_timeline(db, case_id=case.id, actor=current_user, event_type="case_created", title="Case created")
    write_audit(
        db,
        action="case.create",
        target_type="case",
        target_id=case.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
    return _load_case(db, case.id)


@router.get("/{case_id}", response_model=CaseRead)
async def read_case(
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LandCase:
    get_case_for_user(case_id, db, current_user)
    return _load_case(db, case_id)


@router.patch("/{case_id}", response_model=CaseRead)
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LandCase:
    case = get_case_for_user(case_id, db, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    write_audit(
        db,
        action="case.update",
        target_type="case",
        target_id=case.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
    return _load_case(db, case_id)


@router.get("/{case_id}/timeline", response_model=list[TimelineEventRead])
async def case_timeline(
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[TimelineEvent]:
    get_case_for_user(case_id, db, current_user)
    return (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case_id)
        .order_by(TimelineEvent.created_at.asc())
        .all()
    )


@router.post("/{case_id}/ask", response_model=CaseAgentAnswerResponse)
async def ask_case_agent(
    case_id: str,
    payload: CaseAgentQuestionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CaseAgentAnswerResponse:
    case = get_case_for_user(case_id, db, current_user)
    documents = (
        db.query(Document)
        .options(
            selectinload(Document.extracted_fields),
            selectinload(Document.field_corrections),
        )
        .filter(Document.case_id == case.id)
        .all()
    )
    risk_analysis = (
        db.query(RiskAnalysisResult)
        .filter(RiskAnalysisResult.case_id == case.id)
        .order_by(RiskAnalysisResult.created_at.desc())
        .first()
    )
    report = (
        db.query(Report)
        .filter(Report.case_id == case.id)
        .order_by(Report.created_at.desc())
        .first()
    )
    gazette_searches = (
        db.query(GazetteSearch)
        .filter(GazetteSearch.case_id == case.id)
        .order_by(GazetteSearch.created_at.desc())
        .limit(3)
        .all()
    )
    gazette_results = (
        db.query(GazetteSearchResult)
        .filter(GazetteSearchResult.case_id == case.id)
        .order_by(GazetteSearchResult.confidence_score.desc())
        .limit(8)
        .all()
    )
    verification_attempts = (
        db.query(VerificationAttempt)
        .filter(VerificationAttempt.case_id == case.id)
        .order_by(VerificationAttempt.created_at.desc())
        .all()
    )
    answer = answer_case_question(
        case=case,
        documents=documents,
        risk_analysis=risk_analysis,
        report=report,
        gazette_searches=gazette_searches,
        gazette_results=gazette_results,
        verification_attempts=verification_attempts,
        question=payload.question,
    )
    write_audit(
        db,
        action="case.agent_question.ask",
        target_type="case",
        target_id=case.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={"citation_count": len(answer["citations"])},
    )
    db.commit()
    return CaseAgentAnswerResponse.model_validate(answer)


@router.delete("/{case_id}", response_model=DeleteCaseResponse)
async def delete_case(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DeleteCaseResponse:
    case = get_case_for_user(case_id, db, current_user)
    documents = db.query(Document).filter(Document.case_id == case.id).all()
    reports = db.query(Report).filter(Report.case_id == case.id).all()
    storage = get_storage_provider()
    for uri in {item.storage_uri for item in documents if item.storage_uri and item.storage_uri != "pending"} | {
        item.pdf_storage_uri for item in reports if item.pdf_storage_uri
    }:
        storage.delete_uri(uri)

    db.query(AuditLog).filter(AuditLog.case_id == case.id).update(
        {"case_id": None, "target_id": "deleted-case"},
        synchronize_session=False,
    )
    write_audit(
        db,
        action="case.delete",
        target_type="case",
        target_id=case.id,
        actor=current_user,
        request=request,
        metadata={"deleted_documents": len(documents), "deleted_reports": len(reports)},
    )
    db.delete(case)
    db.commit()
    return DeleteCaseResponse(
        status="deleted",
        case_id=case_id,
        deleted_documents=len(documents),
        deleted_reports=len(reports),
    )


def mark_case_ready_if_documents_present(db: Session, case: LandCase) -> None:
    if case.documents and case.status == CaseStatus.DOCUMENTS_PENDING:
        case.status = CaseStatus.READY_FOR_ANALYSIS


def _load_case(db: Session, case_id: str) -> LandCase:
    case = (
        db.query(LandCase)
        .options(
            selectinload(LandCase.documents).selectinload(Document.extracted_fields),
            selectinload(LandCase.documents).selectinload(Document.field_corrections),
        )
        .filter(LandCase.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

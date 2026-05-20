from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.agents.orchestrator import run_case_analysis
from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.models import AnalysisRun, Document, RiskAnalysisResult, RiskFactor, User, VerificationAttempt
from app.schemas import AnalysisRunRead, ReportGenerationRequest, ReportRead, RiskAnalysisRead, RiskFactorRead
from app.services.audit import write_audit, write_timeline
from app.services.risk import run_risk_analysis
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/cases", tags=["analysis"])
api_router = APIRouter(prefix="/api/cases", tags=["analysis"])


@router.post("/{case_id}/analysis", response_model=ReportRead)
async def analyze_case(
    case_id: str,
    payload: ReportGenerationRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReportRead:
    case = get_case_for_user(case_id, db, current_user)
    _ = payload
    run, report = await run_case_analysis(db=db, case=case, storage=get_storage_provider())
    write_audit(
        db,
        action="case.analysis.run",
        target_type="analysis_run",
        target_id=run.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    write_audit(
        db,
        action="report.generate",
        target_type="report",
        target_id=report.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={"analysis_run_id": run.id, "accepted_legal_disclaimer": True},
    )
    db.commit()
    response = ReportRead.model_validate(report)
    response.risk_factors = [
        RiskFactorRead.model_validate(factor)
        for factor in db.query(RiskFactor).filter(RiskFactor.case_id == case.id).all()
    ]
    return response


@router.get("/{case_id}/analysis", response_model=list[AnalysisRunRead])
async def list_analysis_runs(
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AnalysisRun]:
    get_case_for_user(case_id, db, current_user)
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.case_id == case_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )


async def _risk_analysis_response(
    case_id: str,
    request: Request,
    db: Session,
    current_user: User,
) -> RiskAnalysisRead:
    case = get_case_for_user(case_id, db, current_user)
    documents = (
        db.query(Document)
        .options(selectinload(Document.extracted_fields), selectinload(Document.field_corrections))
        .filter(Document.case_id == case.id)
        .all()
    )
    verification_attempts = (
        db.query(VerificationAttempt)
        .filter(VerificationAttempt.case_id == case.id)
        .order_by(VerificationAttempt.created_at.desc())
        .all()
    )
    result, factors = run_risk_analysis(
        case=case,
        documents=documents,
        verification_attempts=verification_attempts,
        duplicate_case_ids=[],
    )
    db.add(result)
    db.flush()
    case.risk_score = result.score
    case.risk_level = result.band
    for factor in factors:
        factor.risk_analysis_id = result.id
        db.add(factor)
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="risk_analysis_completed",
        title=f"Risk analysis completed: {result.band.value}",
        metadata={"risk_analysis_id": result.id, "score": result.score, "version": result.version},
    )
    write_audit(
        db,
        action="case.risk_analysis.run",
        target_type="risk_analysis_result",
        target_id=result.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={"score": result.score, "band": result.band.value, "version": result.version},
    )
    db.commit()
    db.refresh(result)
    return _serialize_risk_analysis(result)


@router.post("/{case_id}/risk-analysis", response_model=RiskAnalysisRead)
async def analyze_case_risk(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RiskAnalysisRead:
    return await _risk_analysis_response(case_id, request, db, current_user)


@api_router.post("/{case_id}/risk-analysis", response_model=RiskAnalysisRead)
async def analyze_case_risk_api(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RiskAnalysisRead:
    return await _risk_analysis_response(case_id, request, db, current_user)


def _serialize_risk_analysis(result: RiskAnalysisResult) -> RiskAnalysisRead:
    payload = result.result_json
    return RiskAnalysisRead(
        id=result.id,
        case_id=result.case_id,
        version=result.version,
        risk_score=result.score,
        risk_level=result.band,
        risk_summary=result.summary,
        risk_factors=payload.get("risk_factors", []),
        recommended_actions=payload.get("recommended_actions", []),
        missing_documents=payload.get("missing_documents", []),
        inconsistencies=payload.get("inconsistencies", []),
        evidence=payload.get("evidence", []),
        result_json=payload,
        created_at=result.created_at,
    )

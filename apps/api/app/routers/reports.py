from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_case_analysis
from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.core.config import settings
from app.models import LandCase, Report, RiskFactor, User
from app.schemas import ReportGenerationRequest, ReportRead, RiskFactorRead
from app.routers.payments import has_successful_report_payment
from app.services.audit import write_audit
from app.services.reporting import report_stale_reasons
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/cases", tags=["reports"])


@router.get("/{case_id}/report", response_model=ReportRead)
async def latest_report(
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReportRead:
    case = get_case_for_user(case_id, db, current_user)
    _ensure_report_unlocked(db, case=case, current_user=current_user)
    report = _latest_report(db, case_id)
    return _report_response(db, case, report)


@router.post("/{case_id}/report", response_model=ReportRead)
async def generate_report(
    case_id: str,
    payload: ReportGenerationRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReportRead:
    case = get_case_for_user(case_id, db, current_user)
    _ensure_report_unlocked(db, case=case, current_user=current_user)
    latest = _optional_latest_report(db, case_id)
    if latest is not None:
        stale_reasons = report_stale_reasons(db, case=case, report=latest)
        if not stale_reasons and not payload.force_regenerate:
            write_audit(
                db,
                action="report.generate.cached",
                target_type="report",
                target_id=latest.id,
                actor=current_user,
                request=request,
                case_id=case.id,
                metadata={"accepted_legal_disclaimer": True},
            )
            db.commit()
            return _report_response(db, case, latest)

    run, report = await run_case_analysis(db=db, case=case, storage=get_storage_provider())
    write_audit(
        db,
        action="report.generate",
        target_type="report",
        target_id=report.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={
            "analysis_run_id": run.id,
            "accepted_legal_disclaimer": True,
            "force_regenerate": payload.force_regenerate,
        },
    )
    db.commit()
    return _report_response(db, case, report)


def _report_response(db: Session, case: LandCase, report: Report) -> ReportRead:
    factors = db.query(RiskFactor).filter(RiskFactor.case_id == case.id).all()
    response = ReportRead.model_validate(report)
    response.risk_factors = [RiskFactorRead.model_validate(factor) for factor in factors]
    response.report_reference = report.content.get("report_id") or report.id
    response.download_url = f"/cases/{case.id}/report.pdf"
    response.stale_reasons = report_stale_reasons(db, case=case, report=report)
    response.is_stale = bool(response.stale_reasons)
    return response


@router.get("/{case_id}/report.pdf")
async def latest_report_pdf(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    case = get_case_for_user(case_id, db, current_user)
    _ensure_report_unlocked(db, case=case, current_user=current_user)
    report = _latest_report(db, case_id)
    stale_reasons = report_stale_reasons(db, case=case, report=report)
    if stale_reasons:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Report is stale. Regenerate it before downloading.",
                "stale_reasons": stale_reasons,
            },
        )
    pdf_bytes = get_storage_provider().read_bytes(report.pdf_storage_uri)
    report_reference = report.content.get("report_id") or report.id
    write_audit(
        db,
        action="download.report_pdf",
        target_type="report",
        target_id=report.id,
        actor=current_user,
        request=request,
        case_id=case_id,
        metadata={"delivery": "authenticated_response"},
    )
    db.commit()
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "content-disposition": f'attachment; filename="mradi-wa-ardhi-{report_reference}.pdf"',
            "cache-control": "no-store",
        },
    )


def _latest_report(db: Session, case_id: str) -> Report:
    report = (
        db.query(Report)
        .filter(Report.case_id == case_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _optional_latest_report(db: Session, case_id: str) -> Report | None:
    return (
        db.query(Report)
        .filter(Report.case_id == case_id)
        .order_by(Report.created_at.desc())
        .first()
    )


def _ensure_report_unlocked(db: Session, *, case: LandCase, current_user: User) -> None:
    if not settings.payment_gate_reports or current_user.role.value == "admin":
        return
    if has_successful_report_payment(db, case_id=case.id, user_id=current_user.id):
        return
    raise HTTPException(
        status_code=402,
        detail={
            "message": "Payment is required before this paid report can be generated, viewed, or downloaded.",
            "payment_status": "required",
            "provider": "mpesa",
        },
    )

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.agents.adk_runtime import build_adk_agents
from app.agents.contracts import (
    CaseProfile,
    ConsistencyAgentInput,
    DocumentDescriptor,
    GazetteSearchAgentInput,
    GazetteSearchAgentOutput,
    IntakeAgentInput,
    LegalSafetyAgentInput,
    OfficialSearchAgentInput,
    OfficialSearchAgentOutput,
    ReportAgentInput,
    RiskScoringAgentInput,
    VisionExtractionAgentInput,
    VisionExtractionAgentOutput,
)
from app.agents.specs import AGENT_SPECS, prompt_hash
from app.agents.system import (
    ConsistencyAgent,
    GazetteSearchAgent,
    IntakeAgent,
    LegalSafetyAgent,
    OfficialSearchAgent,
    ReportAgent,
    RiskScoringAgent,
    VisionExtractionAgent,
)
from app.core.config import settings
from app.domain.enums import AnalysisStatus, CaseStatus, DocumentStatus, VerificationStatus
from app.models import (
    AgentAuditEvent,
    AnalysisRun,
    Document,
    DocumentExtraction,
    ExtractedField,
    FieldCorrection,
    LandCase,
    Report,
    RiskAnalysisResult,
    RiskFactor,
    VerificationAttempt,
)
from app.services.audit import write_timeline
from app.services.reporting import finalize_report_content, render_report_pdf
from app.services.storage import StorageProvider


async def extract_single_document(
    *,
    db: Session,
    document: Document,
    storage: StorageProvider,
) -> VerificationStatus:
    if document.status not in {DocumentStatus.CLEAN, DocumentStatus.EXTRACTED, DocumentStatus.NEEDS_REVIEW}:
        return VerificationStatus.MANUAL_REVIEW_REQUIRED
    document.status = DocumentStatus.EXTRACTING
    document.extraction_status = "running"
    db.flush()
    descriptor = _document_descriptor(document)
    profile = CaseProfile(
        case_id=document.case_id,
        title="Single document extraction",
        required_document_categories=[],
        uploaded_document_categories=[document.category],
    )
    output = await VisionExtractionAgent(storage).run(
        VisionExtractionAgentInput(case_profile=profile, documents=[descriptor])
    )
    _persist_extraction_output(db, output.documents)
    extracted = output.documents[0] if output.documents else None
    document.image_quality_score = extracted.document_quality_score if extracted else None
    document.detected_document_type = extracted.document_type if extracted else document.category.value
    document.document_type_confidence = extracted.extraction_confidence if extracted else 0.0
    document.extraction_warnings = _document_extraction_warnings(extracted) if extracted else [
        {
            "code": "document_extraction_failed",
            "severity": "medium",
            "message": "No reliable structured fields were extracted. Manual review is required.",
        }
    ]
    flag_modified(document, "extraction_warnings")
    document.status = (
        DocumentStatus.EXTRACTED
        if extracted and extracted.extraction_confidence > 0 and not document.extraction_warnings
        else DocumentStatus.NEEDS_REVIEW
    )
    document.extraction_status = "completed" if extracted and extracted.extraction_confidence > 0 else "needs_review"
    db.flush()
    _agent_audit(
        db,
        analysis_run_id=None,
        case_id=document.case_id,
        agent_name="VisionExtractionAgent",
        input_summary={"document_id": document.id, "category": document.category.value},
        output_summary=_dump(output),
    )
    return (
        VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE
        if extracted and extracted.extraction_confidence > 0
        else VerificationStatus.MANUAL_REVIEW_REQUIRED
    )


async def run_case_analysis(
    *,
    db: Session,
    case: LandCase,
    storage: StorageProvider,
) -> tuple[AnalysisRun, Report]:
    run = AnalysisRun(case_id=case.id, status=AnalysisStatus.RUNNING, started_at=datetime.now(UTC).replace(tzinfo=None))
    db.add(run)
    case.status = CaseStatus.ANALYZING
    db.flush()

    adk_agents = build_adk_agents()
    run.agent_trace = {
        "runtime": "google_adk",
        "adk_agents_loaded": sorted(adk_agents.keys()),
        "steps": [],
    }

    try:
        documents = _load_documents(db, case.id)
        descriptors = [_document_descriptor(document) for document in documents]
        intake_input = IntakeAgentInput(
            case_id=case.id,
            title=case.title,
            buyer_name=case.buyer_name,
            seller_name=case.seller_name,
            parcel_number_claimed=case.parcel_number_claimed,
            location_county=case.location_county,
            location=case.location,
            title_number=case.title_number,
            preferred_language=case.preferred_language,
            payment_before_verification=case.payment_before_verification,
            documents=descriptors,
        )
        intake_output = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="IntakeAgent",
            input_payload=intake_input,
            execute=lambda: IntakeAgent().run(intake_input),
        )

        extractable_documents = [
            descriptor
            for descriptor in descriptors
            if descriptor.status in {DocumentStatus.CLEAN.value, DocumentStatus.EXTRACTED.value, DocumentStatus.NEEDS_REVIEW.value}
        ]
        vision_input = VisionExtractionAgentInput(
            case_profile=intake_output.case_profile,
            documents=extractable_documents,
        )
        vision_output: VisionExtractionAgentOutput = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="VisionExtractionAgent",
            input_payload=vision_input,
            execute=lambda: VisionExtractionAgent(storage).run(vision_input),
        )
        _persist_extraction_output(db, vision_output.documents)
        _update_document_extraction_statuses(db, vision_output)
        db.flush()

        consistency_input = ConsistencyAgentInput(
            case_profile=intake_output.case_profile,
            extracted_documents=vision_output.documents,
        )
        consistency_output = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="ConsistencyAgent",
            input_payload=consistency_input,
            execute=lambda: ConsistencyAgent().run(consistency_input),
        )

        official_input = OfficialSearchAgentInput(
            case_profile=intake_output.case_profile,
            extracted_documents=vision_output.documents,
        )
        official_output: OfficialSearchAgentOutput = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="OfficialSearchAgent",
            input_payload=official_input,
            execute=lambda: OfficialSearchAgent().run(official_input),
        )
        _persist_verification_attempt(
            db,
            case_id=case.id,
            adapter_name="uploaded_official_search_certificate",
            status=official_output.verification_status,
            query={"document_category": "land_search_certificate"},
            evidence=_dump(official_output),
            message=official_output.reason,
        )

        gazette_input = GazetteSearchAgentInput(
            case_profile=intake_output.case_profile,
            extracted_documents=vision_output.documents,
        )
        gazette_output: GazetteSearchAgentOutput = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="GazetteSearchAgent",
            input_payload=gazette_input,
            execute=lambda: GazetteSearchAgent().run(gazette_input),
            retries=1,
        )
        _persist_verification_attempt(
            db,
            case_id=case.id,
            adapter_name="kenya_law_gazette",
            status=_gazette_verification_status(gazette_output),
            query={"terms": gazette_output.query_terms},
            evidence=_dump(gazette_output),
            message=gazette_output.reason,
        )

        duplicate_case_ids = _duplicate_case_ids(db, case.id, _primary_parcel(intake_output.case_profile, vision_output.documents))
        risk_input = RiskScoringAgentInput(
            case_profile=intake_output.case_profile,
            extracted_documents=vision_output.documents,
            consistency=consistency_output,
            gazette=gazette_output,
            official_search=official_output,
            duplicate_case_ids=duplicate_case_ids,
        )
        risk_output = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="RiskScoringAgent",
            input_payload=risk_input,
            execute=lambda: RiskScoringAgent().run(risk_input),
        )

        db.query(RiskFactor).filter(RiskFactor.case_id == case.id).delete()
        risk_analysis = RiskAnalysisResult(
            case_id=case.id,
            version="mradi-agent-risk-model-v1",
            engine_version="mradi-risk-engine-v1",
            score=risk_output.score,
            band=risk_output.risk_level,
            summary=_risk_summary(risk_output),
            input_snapshot={"analysis_run_id": run.id, "case_id": case.id},
            result_json=_dump(risk_output),
        )
        db.add(risk_analysis)
        db.flush()
        risk_models = [
            RiskFactor(
                case_id=case.id,
                risk_analysis_id=risk_analysis.id,
                code=factor.code,
                label=factor.label,
                severity=factor.severity,
                points=factor.points,
                evidence={**factor.evidence, "evidence_refs": [ref.model_dump(mode="json") for ref in factor.evidence_refs]},
                recommendation=factor.recommendation,
            )
            for factor in risk_output.risk_factors
        ]
        for factor in risk_models:
            db.add(factor)

        verification_status = _combined_verification_status(
            [
                official_output.verification_status,
                _gazette_verification_status(gazette_output),
            ]
        )
        report_input = ReportAgentInput(
            case_profile=intake_output.case_profile,
            extracted_documents=vision_output.documents,
            consistency=consistency_output,
            gazette=gazette_output,
            official_search=official_output,
            risk=risk_output,
            verification_status=verification_status,
        )
        report_output = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="ReportAgent",
            input_payload=report_input,
            execute=lambda: ReportAgent().run(report_input),
        )

        legal_input = LegalSafetyAgentInput(
            report_content=report_output.content,
            verification_status=verification_status,
        )
        legal_output = await _run_agent(
            db,
            run=run,
            case_id=case.id,
            agent_name="LegalSafetyAgent",
            input_payload=legal_input,
            execute=lambda: LegalSafetyAgent().run(legal_input),
        )

        report_content = finalize_report_content(legal_output.sanitized_content, case_id=case.id, analysis_run_id=run.id)
        pdf_bytes = render_report_pdf(report_content)
        report_uri = f"local://reports/{case.id}/{run.id}.pdf"
        if storage.__class__.__name__ == "GCSStorageProvider":
            report_uri = f"gs://{settings.gcs_bucket}/reports/{case.id}/{run.id}.pdf"
        storage.write_bytes(report_uri, pdf_bytes, "application/pdf")
        report = Report(
            case_id=case.id,
            analysis_run_id=run.id,
            score=risk_output.score,
            band=risk_output.risk_level,
            verification_status=verification_status,
            language=case.preferred_language,
            content=report_content,
            pdf_storage_uri=report_uri,
        )
        db.add(report)
        case.risk_score = risk_output.score
        case.risk_level = risk_output.risk_level
        case.status = CaseStatus.REPORT_READY if risk_output.risk_level.value in {"low", "medium"} else CaseStatus.MANUAL_REVIEW
        run.status = AnalysisStatus.COMPLETED
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        write_timeline(
            db,
            case_id=case.id,
            event_type="analysis_completed",
            title=f"Risk report generated: {risk_output.score}/100 {risk_output.risk_level.value}",
            metadata={"score": risk_output.score, "band": risk_output.risk_level.value},
        )
        db.commit()
        db.refresh(run)
        db.refresh(report)
        return run, report
    except Exception as exc:
        run.status = AnalysisStatus.FAILED
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        case.status = CaseStatus.READY_FOR_ANALYSIS
        db.commit()
        raise


async def _run_agent[T](
    db: Session,
    *,
    run: AnalysisRun,
    case_id: str,
    agent_name: str,
    input_payload: Any,
    execute: Callable[[], T | Awaitable[T]],
    retries: int = 2,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            result = execute()
            if inspect.isawaitable(result):
                result = await result
            _agent_audit(
                db,
                analysis_run_id=run.id,
                case_id=case_id,
                agent_name=agent_name,
                input_summary={"attempt": attempt, "payload": _dump(input_payload)},
                output_summary=_dump(result),
            )
            run.agent_trace.setdefault("steps", []).append(
                {
                    "agent": agent_name,
                    "attempt": attempt,
                    "status": _dump(result).get("status", "completed") if isinstance(_dump(result), dict) else "completed",
                    "confidence": _dump(result).get("confidence") if isinstance(_dump(result), dict) else None,
                }
            )
            flag_modified(run, "agent_trace")
            db.flush()
            return result
        except Exception as exc:
            last_error = exc
            _agent_audit(
                db,
                analysis_run_id=run.id,
                case_id=case_id,
                agent_name=agent_name,
                input_summary={"attempt": attempt, "payload": _dump(input_payload)},
                output_summary={
                    "status": "failed",
                    "failure": {"code": "agent_execution_failed", "message": str(exc), "retryable": attempt <= retries},
                },
            )
            db.flush()
            if attempt > retries:
                raise
    raise RuntimeError(str(last_error) if last_error else f"{agent_name} failed")


def _load_documents(db: Session, case_id: str) -> list[Document]:
    return (
        db.query(Document)
        .options(selectinload(Document.extracted_fields))
        .filter(Document.case_id == case_id)
        .all()
    )


def _document_descriptor(document: Document) -> DocumentDescriptor:
    return DocumentDescriptor(
        id=document.id,
        category=document.category,
        filename=document.filename,
        content_type=document.content_type,
        file_size=document.file_size,
        sha256=document.sha256,
        status=document.status.value if hasattr(document.status, "value") else str(document.status),
        storage_uri=document.storage_uri,
    )


def _persist_extraction_output(db: Session, extracted_documents: list[Any]) -> None:
    for extracted_document in extracted_documents:
        source_document = db.get(Document, extracted_document.document_id)
        if source_document is None:
            continue
        raw_payload = (
            _dump(extracted_document)
            if settings.persist_raw_extraction_payloads
            else _minimized_extraction_payload(extracted_document)
        )
        raw_text = (
            "\n".join(ref.quote for ref in extracted_document.evidence if getattr(ref, "quote", ""))
            if settings.persist_raw_extraction_payloads
            else ""
        )
        extraction = DocumentExtraction(
            case_id=source_document.case_id,
            document_id=source_document.id,
            status="completed",
            engine_version="mradi-extraction-v1",
            model_version=getattr(extracted_document, "extraction_model", "") or "agent-pipeline",
            raw_text=raw_text,
            raw_payload=raw_payload,
            error_message="",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(extraction)
        db.flush()
        db.query(FieldCorrection).filter(
            FieldCorrection.document_id == extracted_document.document_id,
            FieldCorrection.extracted_field_id.is_not(None),
        ).update({"extracted_field_id": None}, synchronize_session=False)
        db.query(ExtractedField).filter(ExtractedField.document_id == extracted_document.document_id).delete()
        for ref in extracted_document.evidence:
            if not ref.field_name or not ref.quote:
                continue
            db.add(
                ExtractedField(
                    document_id=extracted_document.document_id,
                    document_extraction_id=extraction.id,
                    field_name=ref.field_name,
                    value=ref.quote,
                    normalized_value=str(ref.quote).strip().upper(),
                    confidence=ref.confidence,
                    source=ref.source or "agent",
                    page_number=ref.page_number,
                    bounding_box=ref.bounding_box,
                    text_snippet=ref.text_snippet or ref.quote,
                    extraction_metadata=ref.metadata,
                )
            )
        source_document.extraction_status = "completed"


def _update_document_extraction_statuses(db: Session, vision_output: Any) -> None:
    by_id = {document.document_id: document for document in vision_output.documents}
    if not by_id:
        return
    documents = db.query(Document).filter(Document.id.in_(by_id)).all()
    for document in documents:
        extracted = by_id[document.id]
        document.image_quality_score = extracted.document_quality_score
        document.detected_document_type = extracted.document_type or document.category.value
        document.document_type_confidence = extracted.extraction_confidence if extracted.document_type else None
        document.extraction_warnings = _document_extraction_warnings(extracted)
        flag_modified(document, "extraction_warnings")
        document.status = (
            DocumentStatus.EXTRACTED
            if extracted.extraction_confidence > 0 and not document.extraction_warnings
            else DocumentStatus.NEEDS_REVIEW
        )
        document.extraction_status = "completed" if extracted.extraction_confidence > 0 else "needs_review"


def _document_extraction_warnings(extracted: Any) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    failure = getattr(extracted, "failure", None)
    if failure is not None and getattr(failure, "code", "") == "provider_not_configured":
        warnings.append(
            {
                "code": "provider_not_configured",
                "severity": "high",
                "message": "No OCR or vision extraction provider is configured for this file type. Manual review is required.",
            }
        )
    category = extracted.category.value if hasattr(extracted.category, "value") else str(extracted.category)
    if extracted.document_quality_score is not None and extracted.document_quality_score < 0.45:
        warnings.append(
            {
                "code": "poor_image_quality",
                "severity": "medium",
                "message": "Image or OCR quality is low. Ask the user for a clearer scan before relying on extraction.",
            }
        )
    if category in {
        "title_deed",
        "sale_agreement",
        "land_search_certificate",
        "mutation_form",
        "survey_map",
        "kenya_gazette_notice",
    } and not (extracted.parcel_number or extracted.title_number):
        warnings.append(
            {
                "code": "critical_missing_parcel_number",
                "severity": "critical",
                "message": "No parcel or title number was extracted. The user must confirm this field manually.",
            }
        )
    if extracted.extraction_confidence < 0.45:
        warnings.append(
            {
                "code": "document_type_uncertain",
                "severity": "medium",
                "message": "Document type or field extraction confidence is low. Ask the user to confirm the category.",
            }
        )
    return warnings


def _persist_verification_attempt(
    db: Session,
    *,
    case_id: str,
    adapter_name: str,
    status: VerificationStatus,
    query: dict[str, Any],
    evidence: dict[str, Any],
    message: str,
) -> None:
    db.add(
        VerificationAttempt(
            case_id=case_id,
            adapter_name=adapter_name,
            status=status,
            query=query,
            evidence=evidence,
            message=message,
        )
    )


def _primary_parcel(profile: CaseProfile, documents: list[Any]) -> str:
    if profile.parcel_number_claimed:
        return profile.parcel_number_claimed
    for document in documents:
        parcel_number = getattr(document, "parcel_number", "")
        if parcel_number:
            return str(parcel_number)
    return ""


def _duplicate_case_ids(db: Session, case_id: str, parcel_number: str) -> list[str]:
    if not parcel_number:
        return []
    normalized = parcel_number.strip().upper()
    rows = db.query(LandCase).filter(LandCase.id != case_id).all()
    return [
        row.id
        for row in rows
        if row.parcel_number_claimed and row.parcel_number_claimed.strip().upper() == normalized
    ]


def _gazette_verification_status(output: GazetteSearchAgentOutput) -> VerificationStatus:
    if output.gazette_status == "not_checked":
        return VerificationStatus.NOT_CHECKED
    if output.gazette_status == "failed":
        return VerificationStatus.ADAPTER_UNAVAILABLE
    if output.gazette_status == "matches_found":
        conflict_words = ("lost title", "revocation", "caution", "restriction", "rectification", "charge")
        if any(any(word in notice.snippet.lower() for word in conflict_words) for notice in output.notices):
            return VerificationStatus.CONFLICT_FOUND
    return VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE


def _risk_summary(risk_output: Any) -> str:
    actions = getattr(risk_output, "recommended_next_actions", []) or []
    if actions:
        return " ".join(actions[:2])
    return f"{risk_output.risk_level.value.title()} risk with score {risk_output.score}/100."


def _combined_verification_status(statuses: list[VerificationStatus]) -> VerificationStatus:
    if VerificationStatus.CONFLICT_FOUND in statuses:
        return VerificationStatus.CONFLICT_FOUND
    if VerificationStatus.MANUAL_REVIEW_REQUIRED in statuses:
        return VerificationStatus.MANUAL_REVIEW_REQUIRED
    if VerificationStatus.NOT_CHECKED in statuses:
        return VerificationStatus.NOT_CHECKED
    if VerificationStatus.ADAPTER_UNAVAILABLE in statuses:
        return VerificationStatus.ADAPTER_UNAVAILABLE
    if VerificationStatus.VERIFIED in statuses:
        return VerificationStatus.VERIFIED
    return VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE


def _agent_audit(
    db: Session,
    *,
    analysis_run_id: str | None,
    case_id: str | None,
    agent_name: str,
    input_summary: dict[str, Any],
    output_summary: dict[str, Any],
) -> None:
    instruction = next((spec.instruction for spec in AGENT_SPECS if spec.name == agent_name), agent_name)
    db.add(
        AgentAuditEvent(
            analysis_run_id=analysis_run_id,
            case_id=case_id,
            agent_name=agent_name,
            prompt_hash=prompt_hash(instruction),
            input_summary=_redact_for_audit(input_summary),
            output_summary=_redact_for_audit(output_summary),
            model_name=(
                "vertex-agent-engine"
                if settings.vertex_ai_agent_engine_resource
                else "google-adk-local-deterministic"
            ),
        )
    )


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    return value


def _minimized_extraction_payload(extracted_document: Any) -> dict[str, Any]:
    evidence = getattr(extracted_document, "evidence", []) or []
    return {
        "document_id": getattr(extracted_document, "document_id", ""),
        "category": _dump(getattr(extracted_document, "category", "")),
        "document_type": getattr(extracted_document, "document_type", ""),
        "extraction_confidence": getattr(extracted_document, "extraction_confidence", None),
        "document_quality_score": getattr(extracted_document, "document_quality_score", None),
        "field_names": sorted({getattr(ref, "field_name", "") for ref in evidence if getattr(ref, "field_name", "")}),
        "evidence_count": len(evidence),
        "pii_minimized": True,
    }


_AUDIT_REDACT_KEYS = {
    "ai_value",
    "buyer_name",
    "content",
    "corrected_value",
    "email",
    "evidence",
    "extracted_documents",
    "field_value",
    "filename",
    "full_name",
    "id_number",
    "input_snapshot",
    "kra_pin",
    "location",
    "location_county",
    "matched_keywords",
    "notice_title",
    "normalized_value",
    "owner_name",
    "parcel_number",
    "parcel_number_claimed",
    "phone",
    "query",
    "quote",
    "raw_payload",
    "raw_text",
    "report_content",
    "seller_name",
    "snippet",
    "source_url",
    "text_snippet",
    "title",
    "title_number",
    "value",
}


def _redact_for_audit(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_for_audit(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_for_audit(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _AUDIT_REDACT_KEYS:
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = _redact_for_audit(item)
        return redacted
    return value

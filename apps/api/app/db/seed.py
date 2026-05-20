from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.domain.enums import (
    AnalysisStatus,
    CaseStatus,
    DocumentCategory,
    DocumentStatus,
    ReviewRole,
    RiskBand,
    RiskFactorCode,
    UserRole,
    VerificationStatus,
)
from app.models import (
    AgentAuditEvent,
    AnalysisRun,
    ApiKeyOptional,
    AuditLog,
    CaseParticipant,
    Document,
    DocumentExtraction,
    ExtractedField,
    FieldCorrection,
    GazetteSearch,
    GazetteSearchResult,
    LandCase,
    Notification,
    Organization,
    PricingPlanSelection,
    Report,
    ReviewRequest,
    RiskAnalysisResult,
    RiskFactor,
    TimelineEvent,
    User,
)

ORG_ID = "00000000-0000-4000-8000-000000000001"
USER_ID = "00000000-0000-4000-8000-000000000002"
CASE_ID = "00000000-0000-4000-8000-000000000003"
DOCUMENT_ID = "00000000-0000-4000-8000-000000000004"
EXTRACTION_ID = "00000000-0000-4000-8000-000000000005"
FIELD_ID = "00000000-0000-4000-8000-000000000006"
CORRECTION_ID = "00000000-0000-4000-8000-000000000007"
GAZETTE_SEARCH_ID = "00000000-0000-4000-8000-000000000008"
GAZETTE_RESULT_ID = "00000000-0000-4000-8000-000000000009"
ANALYSIS_RUN_ID = "00000000-0000-4000-8000-000000000010"
RISK_ANALYSIS_ID = "00000000-0000-4000-8000-000000000011"
RISK_FACTOR_ID = "00000000-0000-4000-8000-000000000012"
REPORT_ID = "00000000-0000-4000-8000-000000000013"
REVIEW_ID = "00000000-0000-4000-8000-000000000014"
NOTIFICATION_ID = "00000000-0000-4000-8000-000000000015"
PAYMENT_ID = "00000000-0000-4000-8000-000000000016"
API_KEY_ID = "00000000-0000-4000-8000-000000000017"
AUDIT_LOG_ID = "00000000-0000-4000-8000-000000000018"
PARTICIPANT_ID = "00000000-0000-4000-8000-000000000019"
AGENT_AUDIT_ID = "00000000-0000-4000-8000-000000000020"
TIMELINE_ID = "00000000-0000-4000-8000-000000000021"


def seed_dev_data() -> None:
    if settings.is_production:
        raise SystemExit("Refusing to seed development data when APP_ENV=production.")

    db = SessionLocal()
    try:
        _seed(db)
        db.commit()
    finally:
        db.close()


def _seed(db: Session) -> None:
    organization = _upsert(
        db,
        Organization,
        ORG_ID,
        name="Mradi Demo Conveyancing",
        slug="mradi-demo",
    )
    user = _upsert(
        db,
        User,
        USER_ID,
        clerk_user_id="dev_user_mradi_buyer",
        email="buyer@example.test",
        full_name="Amina Wanjiku",
        role=UserRole.BUYER,
        organization_id=organization.id,
    )
    land_case = _upsert(
        db,
        LandCase,
        CASE_ID,
        owner_user_id=user.id,
        organization_id=organization.id,
        title="Kajiado title review",
        location_county="Kajiado",
        location="Ngong",
        parcel_number_claimed="KJD/NGONG/12345",
        title_number="NGONG/12345",
        buyer_name="Amina Wanjiku",
        seller_name="Otieno Holdings Ltd",
        transaction_value=Decimal("7500000.00"),
        status=CaseStatus.REPORT_READY,
        risk_level=RiskBand.MEDIUM,
        risk_score=48,
        preferred_language="en",
        payment_before_verification=False,
    )
    _upsert(
        db,
        CaseParticipant,
        PARTICIPANT_ID,
        case_id=land_case.id,
        user_id=user.id,
        organization_id=organization.id,
        role="buyer",
        full_name="Amina Wanjiku",
        email="buyer@example.test",
        phone="+254700000001",
        id_number="12345678",
        kra_pin="A123456789B",
        metadata_json={"source": "dev_seed"},
    )
    document = _upsert(
        db,
        Document,
        DOCUMENT_ID,
        case_id=land_case.id,
        uploaded_by_user_id=user.id,
        category=DocumentCategory.TITLE_DEED,
        filename="title-deed-demo.pdf",
        file_url="",
        storage_uri="local://dev/title-deed-demo.pdf",
        content_type="application/pdf",
        file_size=245760,
        sha256="dev-seed-title-deed",
        status=DocumentStatus.EXTRACTED,
        extraction_status="completed",
        scan_status="clean",
        image_quality_score=0.92,
        detected_document_type="title_deed",
        document_type_confidence=0.95,
        extraction_warnings=[],
        rejection_reason="",
    )
    extraction = _upsert(
        db,
        DocumentExtraction,
        EXTRACTION_ID,
        case_id=land_case.id,
        document_id=document.id,
        status="completed",
        engine_version="mradi-extraction-v1",
        model_version="dev-fixture",
        raw_text="Title No. NGONG/12345 Parcel No. KJD/NGONG/12345",
        raw_payload={"fixture": True},
        error_message="",
    )
    field = _upsert(
        db,
        ExtractedField,
        FIELD_ID,
        document_id=document.id,
        document_extraction_id=extraction.id,
        field_name="parcel_number",
        value="KJD/NGONG/12345",
        normalized_value="KJD/NGONG/12345",
        confidence=0.93,
        source="dev_seed",
        page_number=1,
        bounding_box={"x": 120, "y": 220, "width": 260, "height": 32},
        text_snippet="Parcel No. KJD/NGONG/12345",
        extraction_metadata={"review_required": False},
    )
    _upsert(
        db,
        FieldCorrection,
        CORRECTION_ID,
        document_id=document.id,
        extracted_field_id=field.id,
        corrected_by_user_id=user.id,
        field_name="parcel_number",
        ai_value="KJD/NGONG/1234S",
        corrected_value="KJD/NGONG/12345",
        normalized_value="KJD/NGONG/12345",
        reason="Corrected OCR confusion between 5 and S.",
        metadata_json={"source": "dev_seed"},
    )
    gazette_search = _upsert(
        db,
        GazetteSearch,
        GAZETTE_SEARCH_ID,
        case_id=land_case.id,
        user_id=user.id,
        query_terms=["KJD/NGONG/12345", "NGONG/12345"],
        county="Kajiado",
        parcel_number="KJD/NGONG/12345",
        title_number="NGONG/12345",
        status="completed",
        result_count=1,
        error_message="",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        GazetteSearchResult,
        GAZETTE_RESULT_ID,
        gazette_search_id=gazette_search.id,
        case_id=land_case.id,
        source_name="Kenya Law Gazette",
        notice_title="Sample notice mentioning Ngong parcel references",
        publication_date="2025-10-03",
        matched_keywords=["NGONG/12345"],
        snippet="Development seed result for Gazette review workflow.",
        source_url="https://new.kenyalaw.org/gazettes/",
        confidence_score=0.62,
        metadata_json={"source": "dev_seed"},
    )
    analysis_run = _upsert(
        db,
        AnalysisRun,
        ANALYSIS_RUN_ID,
        case_id=land_case.id,
        status=AnalysisStatus.COMPLETED,
        error_message="",
        agent_trace={"source": "dev_seed"},
    )
    risk_analysis = _upsert(
        db,
        RiskAnalysisResult,
        RISK_ANALYSIS_ID,
        case_id=land_case.id,
        version="mradi-risk-model-dev",
        engine_version="mradi-risk-engine-v1",
        score=48,
        band=RiskBand.MEDIUM,
        summary="Moderate risk: continue only after official search and professional review.",
        input_snapshot={"case_id": land_case.id},
        result_json={"risk_score": 48, "risk_level": "medium", "risk_factors": []},
    )
    _upsert(
        db,
        RiskFactor,
        RISK_FACTOR_ID,
        case_id=land_case.id,
        risk_analysis_id=risk_analysis.id,
        code=RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH,
        label="Missing official land search",
        severity="high",
        points=20,
        evidence={"source": "dev_seed"},
        recommendation="Upload a fresh official land search before payment.",
    )
    _upsert(
        db,
        Report,
        REPORT_ID,
        case_id=land_case.id,
        analysis_run_id=analysis_run.id,
        score=48,
        band=RiskBand.MEDIUM,
        verification_status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
        language="en",
        content={"summary": "Development report fixture"},
        pdf_storage_uri="local://dev/reports/kajiado-title-review.pdf",
    )
    _upsert(
        db,
        ReviewRequest,
        REVIEW_ID,
        case_id=land_case.id,
        requested_by_user_id=user.id,
        reviewer_role=ReviewRole.ADVOCATE,
        reviewer_email="advocate@example.test",
        note="Please review seller authority before completion.",
        status="requested",
        review_summary="",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        Notification,
        NOTIFICATION_ID,
        user_id=user.id,
        organization_id=organization.id,
        case_id=land_case.id,
        notification_type="risk_analysis_completed",
        title="Risk analysis completed",
        body="Your Kajiado title review is ready.",
        channel="in_app",
        status="unread",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        PricingPlanSelection,
        PAYMENT_ID,
        user_id=user.id,
        organization_id=organization.id,
        case_id=land_case.id,
        plan_key="professional",
        billing_status="selected",
        provider="dev",
        provider_payment_id="dev-payment-001",
        amount=Decimal("2500.00"),
        currency="KES",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        ApiKeyOptional,
        API_KEY_ID,
        user_id=user.id,
        organization_id=organization.id,
        name="Development API key",
        key_prefix="mradi_dev",
        key_hash="dev-only-never-use-in-production",
        scopes=["cases:read", "reports:read"],
        status="active",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        AuditLog,
        AUDIT_LOG_ID,
        actor_user_id=user.id,
        organization_id=organization.id,
        case_id=land_case.id,
        action="dev.seed",
        target_type="case",
        target_id=land_case.id,
        ip_address="127.0.0.1",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        TimelineEvent,
        TIMELINE_ID,
        case_id=land_case.id,
        actor_user_id=user.id,
        event_type="dev_seed_created",
        title="Development seed data created",
        metadata_json={"source": "dev_seed"},
    )
    _upsert(
        db,
        AgentAuditEvent,
        AGENT_AUDIT_ID,
        analysis_run_id=analysis_run.id,
        case_id=land_case.id,
        agent_name="RiskScoringAgent",
        prompt_hash="dev-seed",
        input_summary={"case_id": land_case.id},
        output_summary={"risk_score": 48},
        model_name="dev-fixture",
    )


def _upsert(db: Session, model: type[Any], row_id: str, **values: Any) -> Any:
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
        return row
    for key, value in values.items():
        setattr(row, key, value)
    return row


if __name__ == "__main__":
    seed_dev_data()
    print("Seeded development data for Mradi wa Ardhi.")

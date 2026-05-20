from __future__ import annotations

from app.domain.enums import DocumentCategory, DocumentStatus, RiskBand
from app.models import Document, ExtractedField, LandCase, RiskAnalysisResult
from app.services.case_agent import answer_case_question


def test_case_agent_answers_only_from_case_evidence() -> None:
    case = LandCase(
        id="case-1",
        owner_user_id="user-1",
        title="Q&A case",
        seller_name="John Mwangi",
        parcel_number_claimed="LR 209/1234",
    )
    document = Document(
        id="search",
        case_id=case.id,
        uploaded_by_user_id="user-1",
        category=DocumentCategory.LAND_SEARCH_CERTIFICATE,
        filename="search.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_uri="local://search.pdf",
        status=DocumentStatus.EXTRACTED,
        image_quality_score=0.9,
    )
    document.extracted_fields = [
        ExtractedField(
            document_id=document.id,
            field_name="owner_name",
            value="John Mwangi",
            normalized_value="JOHN MWANGI",
            confidence=0.91,
            source="fixture",
            page_number=1,
            text_snippet="Owner: John Mwangi",
        )
    ]
    document.field_corrections = []
    risk = RiskAnalysisResult(
        case_id=case.id,
        version="test",
        score=20,
        band=RiskBand.LOW,
        summary="Low risk fixture.",
        input_snapshot={},
        result_json={"risk_factors": []},
    )

    response = answer_case_question(
        case=case,
        documents=[document],
        risk_analysis=risk,
        report=None,
        gazette_searches=[],
        gazette_results=[],
        verification_attempts=[],
        question="Who is the owner?",
    )

    assert "does not contain recorded official registry ownership verification" in response["answer"]
    assert response["citations"]
    assert response["verification_status"] == "not_verified_from_official_source"


def test_case_agent_declines_when_no_evidence_matches() -> None:
    case = LandCase(id="case-1", owner_user_id="user-1", title="Q&A case")

    response = answer_case_question(
        case=case,
        documents=[],
        risk_analysis=None,
        report=None,
        gazette_searches=[],
        gazette_results=[],
        verification_attempts=[],
        question="Does the map show beacons?",
    )

    assert "do not have enough" in response["answer"]
    assert response["citations"] == []

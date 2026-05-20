from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.adapters.verification import VerificationResult
from app.agents.contracts import (
    CaseProfile,
    ConsistencyAgentInput,
    DocumentDescriptor,
    EvidenceReference,
    ExtractedDocumentFields,
    GazetteSearchAgentInput,
    IntakeAgentInput,
    LegalSafetyAgentInput,
    OfficialSearchAgentInput,
    ReportAgentInput,
    RiskScoringAgentInput,
    VisionExtractionAgentInput,
)
from app.agents.orchestrator import run_case_analysis
from app.agents.system import (
    CORE_REQUIRED_DOCUMENTS,
    ConsistencyAgent,
    GazetteSearchAgent,
    IntakeAgent,
    LegalSafetyAgent,
    OfficialSearchAgent,
    ReportAgent,
    RiskScoringAgent,
    VisionExtractionAgent,
)
from app.db.session import SessionLocal
from app.domain.enums import DocumentCategory, DocumentStatus, VerificationStatus
from app.models import AgentAuditEvent, Document, LandCase, User


class FakeStorage:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.writes: dict[str, bytes] = {}

    def create_upload_ticket(self, *, document_id: str, filename: str, content_type: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def read_bytes(self, storage_uri: str) -> bytes:
        return self.files[storage_uri]

    def write_bytes(self, storage_uri: str, content: bytes, content_type: str) -> None:
        self.writes[storage_uri] = content

    def create_read_url(self, storage_uri: str, expires_minutes: int = 10) -> str:
        return storage_uri


class FakeGazetteAdapter:
    async def search_terms(self, query_terms: list[str]) -> VerificationResult:
        return VerificationResult(
            adapter_name="fake_gazette",
            status=VerificationStatus.CONFLICT_FOUND,
            query={"terms": query_terms},
            evidence={
                "hits": [
                    {
                        "source": "Kenya Law Gazette",
                        "date": "2025-01-10",
                        "title": "Notice of restriction",
                        "url": "https://example.test/gazette",
                        "snippet": "Restriction registered against LR 209/1234",
                        "confidence": 0.91,
                    }
                ]
            },
            message="Potential Gazette notice conflict found.",
        )


def profile(**overrides: object) -> CaseProfile:
    data = {
        "case_id": "case-1",
        "title": "Kajiado parcel",
        "buyer_name": "Jane Wanjiku",
        "seller_name": "John Mwangi",
        "parcel_number_claimed": "LR 209/1234",
        "county": "Kajiado",
        "preferred_language": "en",
        "payment_before_verification": False,
        "uploaded_document_categories": CORE_REQUIRED_DOCUMENTS,
        "required_document_categories": CORE_REQUIRED_DOCUMENTS,
    }
    data.update(overrides)
    return CaseProfile(**data)


def extracted_doc(
    category: DocumentCategory,
    *,
    document_id: str,
    parcel_number: str = "LR 209/1234",
    title_number: str = "TITLE 1",
    owner_names: list[str] | None = None,
    seller_names: list[str] | None = None,
    document_dates: list[date] | None = None,
    quality: float | None = 0.9,
) -> ExtractedDocumentFields:
    return ExtractedDocumentFields(
        document_id=document_id,
        category=category,
        filename=f"{category.value}.txt",
        document_type=category.value,
        parcel_number=parcel_number,
        title_number=title_number,
        owner_names=owner_names or ["John Mwangi"],
        seller_names=seller_names or ["John Mwangi"],
        document_dates=document_dates or [],
        search_dates=document_dates if category == DocumentCategory.LAND_SEARCH_CERTIFICATE else [],
        document_quality_score=quality,
        extraction_confidence=0.86,
        evidence=[
            EvidenceReference(
                document_id=document_id,
                document_category=category,
                field_name="parcel_number",
                quote=parcel_number,
                source="test",
                confidence=0.9,
            )
        ],
    )


def test_intake_agent_creates_case_profile_and_missing_inputs() -> None:
    output = IntakeAgent().run(
        payload=IntakeAgentInput(
            case_id="case-1",
            title="Missing parcel",
            buyer_name="Jane",
            seller_name="",
            parcel_number_claimed="",
            location_county="Kajiado",
            documents=[],
        )
    )
    assert output.case_profile.missing_inputs == ["seller_name", "parcel_number_claimed"]
    assert output.confidence < 0.8


def test_vision_extraction_agent_extracts_fields_with_citations() -> None:
    descriptor = DocumentDescriptor(
        id="doc-1",
        category=DocumentCategory.TITLE_DEED,
        filename="title.txt",
        content_type="text/plain",
        storage_uri="local://title.txt",
    )
    text = (
        b"Title Number: TITLE 1\nParcel No: LR 209/1234\nOwner: John Mwangi\n"
        b"ID No: 12345678\nRegistry: Nairobi\nSeal present\nSignature present"
    )
    output = asyncio.run(
        VisionExtractionAgent(FakeStorage({"local://title.txt": text})).run(
            VisionExtractionAgentInput(case_profile=profile(), documents=[descriptor])
        )
    )
    assert output.documents[0].parcel_number == "LR 209/1234"
    assert output.documents[0].title_number == "TITLE 1"
    assert output.documents[0].seals_present is True
    assert output.documents[0].evidence
    assert output.documents[0].evidence[0].page_number == 1
    assert output.documents[0].evidence[0].text_snippet


def test_consistency_agent_detects_missing_docs_mismatch_and_stale_search() -> None:
    old_search_date = date.today() - timedelta(days=45)
    output = ConsistencyAgent().run(
        ConsistencyAgentInput(
            case_profile=profile(uploaded_document_categories=[DocumentCategory.TITLE_DEED, DocumentCategory.LAND_SEARCH_CERTIFICATE]),
            extracted_documents=[
                extracted_doc(DocumentCategory.TITLE_DEED, document_id="title", parcel_number="LR 1"),
                extracted_doc(
                    DocumentCategory.LAND_SEARCH_CERTIFICATE,
                    document_id="search",
                    parcel_number="LR 2",
                    document_dates=[old_search_date],
                ),
            ],
        )
    )
    assert output.missing_required_documents
    assert any(mismatch.code == "parcel_number_mismatch" for mismatch in output.mismatches)
    assert output.old_search_certificate is True


def test_gazette_search_agent_never_fabricates_and_reports_not_checked() -> None:
    no_terms = asyncio.run(
        GazetteSearchAgent().run(
            GazetteSearchAgentInput(
                case_profile=profile(parcel_number_claimed="", county=""),
                extracted_documents=[],
            )
        )
    )
    assert no_terms.gazette_status == "not_checked"
    assert not no_terms.notices

    found = asyncio.run(
        GazetteSearchAgent(FakeGazetteAdapter()).run(
            GazetteSearchAgentInput(case_profile=profile(), extracted_documents=[])
        )
    )
    assert found.gazette_status == "matches_found"
    assert found.notices[0].source == "fake_gazette"


def test_official_search_agent_marks_missing_and_parses_uploaded_certificate() -> None:
    missing = OfficialSearchAgent().run(
        OfficialSearchAgentInput(case_profile=profile(), extracted_documents=[])
    )
    assert missing.official_search_status == "missing"
    assert missing.verification_status == VerificationStatus.MANUAL_REVIEW_REQUIRED

    parsed = OfficialSearchAgent().run(
        OfficialSearchAgentInput(
            case_profile=profile(),
            extracted_documents=[
                extracted_doc(DocumentCategory.LAND_SEARCH_CERTIFICATE, document_id="search", document_dates=[date.today()])
            ],
        )
    )
    assert parsed.official_search_status == "parsed"
    assert parsed.verification_status == VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE


def test_risk_report_and_legal_safety_agents() -> None:
    consistency = ConsistencyAgent().run(
        ConsistencyAgentInput(case_profile=profile(), extracted_documents=[])
    )
    official = OfficialSearchAgent().run(
        OfficialSearchAgentInput(case_profile=profile(), extracted_documents=[])
    )
    gazette = asyncio.run(
        GazetteSearchAgent().run(
            GazetteSearchAgentInput(case_profile=profile(parcel_number_claimed="", county=""), extracted_documents=[])
        )
    )
    risk = RiskScoringAgent().run(
        RiskScoringAgentInput(
            case_profile=profile(uploaded_document_categories=[]),
            extracted_documents=[],
            consistency=consistency,
            gazette=gazette,
            official_search=official,
            duplicate_case_ids=[],
        )
    )
    report = ReportAgent().run(
        ReportAgentInput(
            case_profile=profile(uploaded_document_categories=[]),
            extracted_documents=[],
            consistency=consistency,
            gazette=gazette,
            official_search=official,
            risk=risk,
            verification_status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
        )
    )
    legal = LegalSafetyAgent().run(
        LegalSafetyAgentInput(
            report_content={**report.content, "unsafe": "ownership verified"},
            verification_status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
        )
    )
    assert risk.score > 0
    assert report.content["document_checklist"]
    assert legal.disclaimer.startswith("This report is an AI-assisted risk analysis.")
    assert legal.blocked_claims


def test_orchestrator_persists_every_agent_output(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class NoMatchGazetteAdapter:
        async def search_terms(self, query_terms: list[str]) -> VerificationResult:
            return VerificationResult(
                adapter_name="fake_gazette",
                status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
                query={"terms": query_terms},
                evidence={"hits": []},
                message="No Gazette matches in fixture.",
            )

    monkeypatch.setattr("app.agents.system.KenyaGazetteAdapter", NoMatchGazetteAdapter)
    db = SessionLocal()
    try:
        user = User(clerk_user_id="agent-user", email="agent@example.test", full_name="Agent User")
        db.add(user)
        db.flush()
        land_case = LandCase(
            owner_user_id=user.id,
            title="Agent persisted case",
            buyer_name="Jane Wanjiku",
            seller_name="John Mwangi",
            parcel_number_claimed="LR 209/1234",
            location_county="Kajiado",
        )
        db.add(land_case)
        db.flush()
        document = Document(
            case_id=land_case.id,
            uploaded_by_user_id=user.id,
            category=DocumentCategory.TITLE_DEED,
            filename="title.txt",
            content_type="text/plain",
            file_size=100,
            sha256="",
            storage_uri="local://clean/title.txt",
            status=DocumentStatus.CLEAN,
        )
        db.add(document)
        db.commit()

        storage = FakeStorage(
            {
                "local://clean/title.txt": (
                    b"Title Number: TITLE 1\nParcel No: LR 209/1234\nOwner: John Mwangi\n"
                    b"Registry: Kajiado\nSignature present\nSeal present"
                )
            }
        )
        run, report = asyncio.run(run_case_analysis(db=db, case=land_case, storage=storage))
        agent_names = {
            event.agent_name
            for event in db.query(AgentAuditEvent).filter(AgentAuditEvent.analysis_run_id == run.id).all()
        }
        assert {
            "IntakeAgent",
            "VisionExtractionAgent",
            "ConsistencyAgent",
            "GazetteSearchAgent",
            "OfficialSearchAgent",
            "RiskScoringAgent",
            "ReportAgent",
            "LegalSafetyAgent",
        }.issubset(agent_names)
        assert report.content["legal_disclaimer"].startswith("This report is an AI-assisted risk analysis.")
        assert storage.writes
    finally:
        db.close()

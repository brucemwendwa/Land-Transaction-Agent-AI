from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.adapters.verification import VerificationResult
from app.agents.contracts import (
    CaseProfile,
    ConsistencyAgentInput,
    EvidenceReference,
    ExtractedDocumentFields,
    GazetteNotice,
    GazetteSearchAgentInput,
    GazetteSearchAgentOutput,
    OfficialSearchAgentInput,
    RiskScoringAgentInput,
    RiskScoringAgentOutput,
)
from app.agents.system import (
    CORE_REQUIRED_DOCUMENTS,
    ConsistencyAgent,
    GazetteSearchAgent,
    OfficialSearchAgent,
    RiskScoringAgent,
)
from app.domain.enums import DocumentCategory, RiskBand, RiskFactorCode, VerificationStatus


def case_profile(*, uploaded: list[DocumentCategory], payment: bool = False) -> CaseProfile:
    return CaseProfile(
        case_id="case-eval",
        title="Evaluation parcel",
        buyer_name="Jane Wanjiku",
        seller_name="John Mwangi",
        parcel_number_claimed="LR 209/1234",
        county="Kajiado",
        payment_before_verification=payment,
        uploaded_document_categories=uploaded,
        required_document_categories=CORE_REQUIRED_DOCUMENTS,
    )


def doc(
    category: DocumentCategory,
    document_id: str,
    *,
    parcel: str = "LR 209/1234",
    owner: str = "John Mwangi",
    quality: float = 0.9,
    suspicious: bool = False,
    search_date: date | None = None,
) -> ExtractedDocumentFields:
    evidence = [
        EvidenceReference(
            document_id=document_id,
            document_category=category,
            field_name="parcel_number",
            quote=parcel,
            source="fixture",
            confidence=0.9,
        )
    ]
    return ExtractedDocumentFields(
        document_id=document_id,
        category=category,
        filename=f"{category.value}.txt",
        document_type=category.value,
        parcel_number=parcel,
        owner_names=[owner],
        seller_names=[owner],
        document_dates=[search_date] if search_date else [],
        search_dates=[search_date] if search_date and category == DocumentCategory.LAND_SEARCH_CERTIFICATE else [],
        document_quality_score=quality,
        extraction_confidence=0.86,
        suspicious_edit_signals=["overwritten"] if suspicious else [],
        evidence=evidence,
    )


def risk_for(
    *,
    uploaded: list[DocumentCategory],
    documents: list[ExtractedDocumentFields],
    payment: bool = False,
    gazette_conflict: bool = False,
) -> RiskScoringAgentOutput:
    profile = case_profile(uploaded=uploaded, payment=payment)
    consistency = ConsistencyAgent().run(
        ConsistencyAgentInput(case_profile=profile, extracted_documents=documents)
    )
    official = OfficialSearchAgent().run(
        OfficialSearchAgentInput(case_profile=profile, extracted_documents=documents)
    )
    gazette = GazetteSearchAgentOutput(
        gazette_status="matches_found" if gazette_conflict else "checked_no_match",
        query_terms=["LR 209/1234"],
        notices=[
            GazetteNotice(
                source="Kenya Law Gazette",
                date="2025-01-01",
                title="Restriction notice",
                url="https://example.test",
                snippet="Restriction against LR 209/1234",
                confidence=0.9,
            )
        ]
        if gazette_conflict
        else [],
        reason="fixture",
    )
    return RiskScoringAgent().run(
        RiskScoringAgentInput(
            case_profile=profile,
            extracted_documents=documents,
            consistency=consistency,
            gazette=gazette,
            official_search=official,
            duplicate_case_ids=[],
        )
    )


def score_for(
    *,
    uploaded: list[DocumentCategory],
    documents: list[ExtractedDocumentFields],
    payment: bool = False,
    gazette_conflict: bool = False,
) -> RiskBand:
    return risk_for(
        uploaded=uploaded,
        documents=documents,
        payment=payment,
        gazette_conflict=gazette_conflict,
    ).risk_level


def codes_for(
    *,
    uploaded: list[DocumentCategory],
    documents: list[ExtractedDocumentFields],
    payment: bool = False,
    gazette_conflict: bool = False,
) -> set[RiskFactorCode]:
    return {
        factor.code
        for factor in risk_for(
            uploaded=uploaded,
            documents=documents,
            payment=payment,
            gazette_conflict=gazette_conflict,
        ).risk_factors
    }


def test_low_risk_evaluation_case() -> None:
    documents = [
        doc(category, f"doc-{category.value}", search_date=date.today())
        for category in CORE_REQUIRED_DOCUMENTS
    ]
    risk = risk_for(uploaded=CORE_REQUIRED_DOCUMENTS, documents=documents)
    assert risk.risk_level == RiskBand.LOW
    assert risk.risk_factors == []


def test_medium_risk_evaluation_case() -> None:
    uploaded = [DocumentCategory.TITLE_DEED, DocumentCategory.SALE_AGREEMENT]
    documents = [doc(DocumentCategory.TITLE_DEED, "title"), doc(DocumentCategory.SALE_AGREEMENT, "sale")]
    assert score_for(uploaded=uploaded, documents=documents) == RiskBand.MEDIUM
    assert RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH in codes_for(uploaded=uploaded, documents=documents)


def test_high_risk_evaluation_case() -> None:
    uploaded = [DocumentCategory.TITLE_DEED, DocumentCategory.SALE_AGREEMENT, DocumentCategory.LAND_SEARCH_CERTIFICATE]
    documents = [
        doc(DocumentCategory.TITLE_DEED, "title"),
        doc(DocumentCategory.SALE_AGREEMENT, "sale"),
        doc(
            DocumentCategory.LAND_SEARCH_CERTIFICATE,
            "search",
            search_date=date.today() - timedelta(days=45),
        ),
    ]
    assert score_for(uploaded=uploaded, documents=documents, payment=True) == RiskBand.HIGH
    assert RiskFactorCode.STALE_SEARCH_CERTIFICATE in codes_for(uploaded=uploaded, documents=documents, payment=True)


def test_critical_risk_evaluation_case() -> None:
    uploaded = [DocumentCategory.TITLE_DEED, DocumentCategory.SALE_AGREEMENT]
    documents = [
        doc(DocumentCategory.TITLE_DEED, "title", parcel="LR 1", suspicious=True),
        doc(DocumentCategory.SALE_AGREEMENT, "sale", parcel="LR 2"),
    ]
    assert score_for(uploaded=uploaded, documents=documents, payment=True, gazette_conflict=True) == RiskBand.CRITICAL
    assert RiskFactorCode.GAZETTE_NOTICE_CONFLICT in codes_for(
        uploaded=uploaded,
        documents=documents,
        payment=True,
        gazette_conflict=True,
    )


def test_agent_evaluation_flags_missing_title_deed() -> None:
    uploaded = [category for category in CORE_REQUIRED_DOCUMENTS if category != DocumentCategory.TITLE_DEED]
    documents = [doc(category, f"doc-{category.value}", search_date=date.today()) for category in uploaded]

    assert RiskFactorCode.MISSING_TITLE_DEED in codes_for(uploaded=uploaded, documents=documents)


def test_agent_evaluation_flags_multiple_owners_one_seller() -> None:
    uploaded = CORE_REQUIRED_DOCUMENTS
    documents = [
        doc(category, f"doc-{category.value}", search_date=date.today())
        for category in CORE_REQUIRED_DOCUMENTS
        if category != DocumentCategory.LAND_SEARCH_CERTIFICATE
    ]
    documents.append(
        doc(
            DocumentCategory.LAND_SEARCH_CERTIFICATE,
            "search",
            owner="John Mwangi",
            search_date=date.today(),
        ).model_copy(update={"owner_names": ["John Mwangi", "Grace Achieng"]})
    )

    codes = codes_for(uploaded=uploaded, documents=documents)

    assert RiskFactorCode.MULTIPLE_OWNERS_ONE_SELLER in codes
    assert RiskFactorCode.MISSING_SPOUSAL_CONSENT in codes


def test_agent_evaluation_flags_power_of_attorney_risk() -> None:
    uploaded = [*CORE_REQUIRED_DOCUMENTS, DocumentCategory.POWER_OF_ATTORNEY]
    documents = [
        doc(category, f"doc-{category.value}", search_date=date.today())
        for category in CORE_REQUIRED_DOCUMENTS
    ]
    documents.append(doc(DocumentCategory.POWER_OF_ATTORNEY, "poa"))

    assert RiskFactorCode.POWER_OF_ATTORNEY_UNVERIFIED in codes_for(uploaded=uploaded, documents=documents)


def test_gazette_agent_reports_search_failed_without_fabricating_notice() -> None:
    class FailingGazetteAdapter:
        async def search_terms(self, query_terms: list[str]) -> VerificationResult:
            raise TimeoutError(f"timeout for {query_terms[0]}")

    output = asyncio.run(
        GazetteSearchAgent(FailingGazetteAdapter()).run(
            GazetteSearchAgentInput(case_profile=case_profile(uploaded=CORE_REQUIRED_DOCUMENTS), extracted_documents=[])
        )
    )

    assert output.status == "failed"
    assert output.gazette_status == "not_checked"
    assert output.notices == []
    assert output.failure is not None
    assert output.failure.retryable is True


def test_gazette_agent_no_match_is_distinct_from_failed_search() -> None:
    class NoMatchGazetteAdapter:
        async def search_terms(self, query_terms: list[str]) -> VerificationResult:
            return VerificationResult(
                adapter_name="fixture",
                status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
                query={"terms": query_terms},
                evidence={"hits": []},
                message="No Gazette match in fixture.",
            )

    output = asyncio.run(
        GazetteSearchAgent(NoMatchGazetteAdapter()).run(
            GazetteSearchAgentInput(case_profile=case_profile(uploaded=CORE_REQUIRED_DOCUMENTS), extracted_documents=[])
        )
    )

    assert output.status == "completed"
    assert output.gazette_status == "checked_no_match"
    assert output.notices == []

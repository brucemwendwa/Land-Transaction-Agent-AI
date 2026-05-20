from __future__ import annotations

from datetime import date, timedelta

from app.domain.enums import DocumentCategory, DocumentStatus, RiskBand, RiskFactorCode, VerificationStatus
from app.models import Document, ExtractedField, LandCase, VerificationAttempt
from app.services.risk import build_risk_analysis_payload, build_risk_factors


def land_case(**overrides: object) -> LandCase:
    values = {
        "id": "case-1",
        "owner_user_id": "user-1",
        "title": "Risk case",
        "buyer_name": "Jane Wanjiku",
        "seller_name": "John Mwangi",
        "parcel_number_claimed": "LR 209/1234",
        "payment_before_verification": False,
    }
    values.update(overrides)
    return LandCase(**values)


def doc(
    category: DocumentCategory,
    document_id: str,
    *,
    parcel: str = "LR 209/1234",
    owner: str = "John Mwangi",
    seller: str = "John Mwangi",
    document_date: date | None = None,
    quality: float = 0.9,
    fields: dict[str, str] | None = None,
) -> Document:
    document = Document(
        id=document_id,
        case_id="case-1",
        uploaded_by_user_id="user-1",
        category=category,
        filename=f"{category.value}.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_uri=f"local://clean/{document_id}.pdf",
        status=DocumentStatus.EXTRACTED,
        image_quality_score=quality,
    )
    base_fields: dict[str, str] = {}
    if category in {
        DocumentCategory.TITLE_DEED,
        DocumentCategory.SALE_AGREEMENT,
        DocumentCategory.LAND_SEARCH_CERTIFICATE,
        DocumentCategory.MUTATION_FORM,
        DocumentCategory.SURVEY_MAP,
    }:
        base_fields["parcel_number"] = parcel
    if category in {DocumentCategory.TITLE_DEED, DocumentCategory.LAND_SEARCH_CERTIFICATE}:
        base_fields["owner_name"] = owner
    if category == DocumentCategory.SALE_AGREEMENT:
        base_fields["seller_name"] = seller
        base_fields["signatures_present"] = "true"
        base_fields["seals_present"] = "true"
    if category == DocumentCategory.KRA_PIN_CERTIFICATE:
        base_fields["kra_pin"] = "A123456789B"
    if document_date:
        base_fields["document_date"] = document_date.isoformat()
    base_fields.update(fields or {})
    document.extracted_fields = [
        ExtractedField(
            id=f"{document_id}-{field_name}",
            document_id=document_id,
            field_name=field_name,
            value=value,
            normalized_value=value.upper(),
            confidence=0.9,
            source="fixture",
            page_number=1,
            text_snippet=f"{field_name}: {value}",
        )
        for field_name, value in base_fields.items()
    ]
    document.field_corrections = []
    return document


def core_documents(*, search_date: date | None = None) -> list[Document]:
    return [
        doc(DocumentCategory.TITLE_DEED, "title"),
        doc(DocumentCategory.SALE_AGREEMENT, "sale"),
        doc(DocumentCategory.NATIONAL_ID_OR_PASSPORT, "id", fields={"id_number": "12345678"}),
        doc(DocumentCategory.KRA_PIN_CERTIFICATE, "kra"),
        doc(DocumentCategory.LAND_SEARCH_CERTIFICATE, "search", document_date=search_date or date.today()),
        doc(DocumentCategory.CONSENT_TO_TRANSFER, "consent"),
        doc(DocumentCategory.RATES_CLEARANCE_CERTIFICATE, "rates"),
        doc(DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE, "rent"),
    ]


def analyze(
    *,
    case: LandCase | None = None,
    documents: list[Document] | None = None,
    attempts: list[VerificationAttempt] | None = None,
) -> dict:
    return build_risk_analysis_payload(
        case=case or land_case(),
        documents=documents if documents is not None else core_documents(),
        verification_attempts=attempts or [],
    )


def codes(payload: dict) -> set[str]:
    return {factor["code"] for factor in payload["risk_factors"]}


def test_low_risk_case() -> None:
    payload = analyze()
    assert payload["risk_score"] == 0
    assert payload["risk_level"] == RiskBand.LOW.value
    assert payload["risk_factors"] == []


def test_medium_risk_case() -> None:
    documents = [item for item in core_documents() if item.category != DocumentCategory.KRA_PIN_CERTIFICATE]
    documents[0].image_quality_score = 0.4
    documents[1] = doc(DocumentCategory.SALE_AGREEMENT, "sale", fields={"signatures_present": "", "seals_present": ""})
    payload = analyze(case=land_case(payment_before_verification=True), documents=documents)
    assert payload["risk_level"] == RiskBand.MEDIUM.value
    assert RiskFactorCode.LOW_DOCUMENT_CONFIDENCE.value in codes(payload)
    assert RiskFactorCode.MISSING_KRA_PIN.value in codes(payload)


def test_high_risk_case() -> None:
    documents = [
        doc(DocumentCategory.TITLE_DEED, "title"),
        doc(DocumentCategory.SALE_AGREEMENT, "sale"),
        doc(
            DocumentCategory.LAND_SEARCH_CERTIFICATE,
            "search",
            document_date=date.today() - timedelta(days=45),
        ),
    ]
    payload = analyze(case=land_case(payment_before_verification=True), documents=documents)
    assert payload["risk_level"] == RiskBand.HIGH.value
    assert RiskFactorCode.STALE_SEARCH_CERTIFICATE.value in codes(payload)
    assert RiskFactorCode.PAYMENT_BEFORE_VERIFICATION.value in codes(payload)


def test_critical_risk_case() -> None:
    documents = core_documents()
    documents[0] = doc(DocumentCategory.TITLE_DEED, "title", parcel="LR 1")
    documents[1] = doc(DocumentCategory.SALE_AGREEMENT, "sale", parcel="LR 2")
    documents[4] = doc(DocumentCategory.LAND_SEARCH_CERTIFICATE, "search", parcel="LR 3")
    payload = analyze(documents=documents)
    assert payload["risk_level"] == RiskBand.CRITICAL.value
    assert payload["critical_floor_applied"] is True
    assert RiskFactorCode.PARCEL_NUMBER_MISMATCH.value in codes(payload)


def test_missing_documents_case() -> None:
    payload = analyze(documents=[doc(DocumentCategory.SALE_AGREEMENT, "sale")])
    assert payload["risk_level"] == RiskBand.CRITICAL.value
    assert RiskFactorCode.MISSING_TITLE_DEED.value in codes(payload)
    assert RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH.value in codes(payload)
    assert any(item["category"] == "title_deed" for item in payload["missing_documents"])


def test_gazette_conflict_case() -> None:
    attempt = VerificationAttempt(
        case_id="case-1",
        adapter_name="kenya_law_gazette",
        status=VerificationStatus.CONFLICT_FOUND,
        query={"terms": ["LR 209/1234"]},
        evidence={"hits": [{"snippet": "Compulsory acquisition of LR 209/1234"}]},
        message="Compulsory acquisition notice found.",
    )
    payload = analyze(documents=core_documents(), attempts=[attempt])
    assert payload["risk_level"] == RiskBand.CRITICAL.value
    assert RiskFactorCode.GAZETTE_NOTICE_CONFLICT.value in codes(payload)


def test_risk_engine_compatibility_helper_flags_unverified_status() -> None:
    case = land_case(parcel_number_claimed="LR 1")
    title = doc(DocumentCategory.TITLE_DEED, "title", parcel="LR 2")
    score, band, factors = build_risk_factors(
        case,
        [title],
        [VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE],
    )
    factor_codes = {factor.code for factor in factors}
    assert score > 0
    assert band in {RiskBand.MEDIUM, RiskBand.HIGH, RiskBand.CRITICAL}
    assert RiskFactorCode.PARCEL_NUMBER_MISMATCH in factor_codes
    assert RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH in factor_codes

from __future__ import annotations

from datetime import date, timedelta

from app.domain.enums import DocumentCategory, RiskBand, RiskFactorCode, VerificationStatus
from app.models import VerificationAttempt
from app.services.risk import build_risk_analysis_payload
from tests.factories import make_case, make_core_documents, make_correction, make_document


def factor_codes(payload: dict) -> set[str]:
    return {factor["code"] for factor in payload["risk_factors"]}


def analyze(
    *,
    documents: list | None = None,
    attempts: list[VerificationAttempt] | None = None,
    payment_before_verification: bool = False,
) -> dict:
    return build_risk_analysis_payload(
        case=make_case(payment_before_verification=payment_before_verification),
        documents=documents if documents is not None else make_core_documents(),
        verification_attempts=attempts or [],
    )


def test_clean_low_risk_transaction_has_no_hidden_risk_factors() -> None:
    payload = analyze()

    assert payload["risk_score"] == 0
    assert payload["risk_level"] == RiskBand.LOW.value
    assert payload["risk_factors"] == []
    assert payload["missing_documents"] == []
    assert payload["critical_floor_applied"] is False


def test_missing_title_deed_blocks_clean_risk_result() -> None:
    documents = [document for document in make_core_documents() if document.category != DocumentCategory.TITLE_DEED]

    payload = analyze(documents=documents)

    assert RiskFactorCode.MISSING_TITLE_DEED.value in factor_codes(payload)
    assert any(item["category"] == DocumentCategory.TITLE_DEED.value for item in payload["missing_documents"])
    assert payload["risk_level"] == RiskBand.CRITICAL.value


def test_seller_name_mismatch_is_critical_and_evidence_backed() -> None:
    documents = make_core_documents()
    documents[4] = make_document(DocumentCategory.LAND_SEARCH_CERTIFICATE, "search", owner="Grace Achieng", document_date=date.today())

    payload = analyze(documents=documents)
    factors = {factor["code"]: factor for factor in payload["risk_factors"]}

    assert RiskFactorCode.SELLER_NAME_MISMATCH.value in factors
    assert payload["risk_level"] == RiskBand.CRITICAL.value
    assert {item["value"] for item in factors[RiskFactorCode.SELLER_NAME_MISMATCH.value]["evidence"]} >= {
        "Grace Achieng",
        "John Mwangi",
    }


def test_parcel_number_mismatch_compares_case_title_sale_and_search() -> None:
    documents = make_core_documents()
    documents[0] = make_document(DocumentCategory.TITLE_DEED, "title", parcel="LR 209/1234")
    documents[1] = make_document(DocumentCategory.SALE_AGREEMENT, "sale", parcel="LR 209/9999")
    documents[4] = make_document(DocumentCategory.LAND_SEARCH_CERTIFICATE, "search", parcel="LR 209/1234", document_date=date.today())

    payload = analyze(documents=documents)

    assert RiskFactorCode.PARCEL_NUMBER_MISMATCH.value in factor_codes(payload)
    assert payload["critical_floor_applied"] is True
    assert any(item["code"] == "parcel_title_mismatch" for item in payload["inconsistencies"])


def test_search_certificate_older_than_30_days_requires_fresh_search() -> None:
    payload = analyze(documents=make_core_documents(search_date=date.today() - timedelta(days=31)))

    assert RiskFactorCode.STALE_SEARCH_CERTIFICATE.value in factor_codes(payload)
    stale = next(factor for factor in payload["risk_factors"] if factor["code"] == RiskFactorCode.STALE_SEARCH_CERTIFICATE.value)
    assert stale["search_dates"] == [(date.today() - timedelta(days=31)).isoformat()]
    assert "fresh official search" in stale["recommendation"].lower()


def test_gazette_possible_conflict_escalates_to_critical_review() -> None:
    attempt = VerificationAttempt(
        case_id="case-1",
        adapter_name="kenya_law_gazette",
        status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
        query={"terms": ["LR 209/1234"]},
        evidence={"hits": [{"snippet": "Possible compulsory acquisition and road reserve notice for LR 209/1234"}]},
        message="Possible Gazette conflict found.",
    )

    payload = analyze(attempts=[attempt])

    assert RiskFactorCode.GAZETTE_NOTICE_CONFLICT.value in factor_codes(payload)
    assert payload["risk_level"] == RiskBand.CRITICAL.value


def test_poor_quality_document_is_not_treated_as_reliable() -> None:
    documents = make_core_documents()
    documents[0].image_quality_score = 0.2

    payload = analyze(documents=documents)

    assert RiskFactorCode.POOR_IMAGE_QUALITY.value in factor_codes(payload)
    assert payload["risk_level"] == RiskBand.CRITICAL.value
    assert payload["critical_floor_applied"] is True


def test_missing_consent_to_transfer_is_called_out_even_when_other_docs_exist() -> None:
    documents = [document for document in make_core_documents() if document.category != DocumentCategory.CONSENT_TO_TRANSFER]

    payload = analyze(documents=documents)

    assert RiskFactorCode.MISSING_CONSENT_TO_TRANSFER.value in factor_codes(payload)
    assert any(item["category"] == DocumentCategory.CONSENT_TO_TRANSFER.value for item in payload["missing_documents"])


def test_multiple_registered_owners_with_one_seller_requires_all_owner_authority() -> None:
    documents = make_core_documents()
    documents[4] = make_document(
        DocumentCategory.LAND_SEARCH_CERTIFICATE,
        "search",
        owner="John Mwangi",
        document_date=date.today(),
        fields=[("owner_name", "Grace Achieng")],
    )

    payload = analyze(documents=documents)

    assert RiskFactorCode.MULTIPLE_OWNERS_ONE_SELLER.value in factor_codes(payload)
    assert RiskFactorCode.SELLER_NAME_MISMATCH.value not in factor_codes(payload)
    assert RiskFactorCode.MISSING_SPOUSAL_CONSENT.value in factor_codes(payload)


def test_power_of_attorney_without_supporting_details_is_critical() -> None:
    documents = [
        *make_core_documents(),
        make_document(DocumentCategory.POWER_OF_ATTORNEY, "poa", fields=[]),
    ]

    payload = analyze(documents=documents)

    assert RiskFactorCode.POWER_OF_ATTORNEY_UNVERIFIED.value in factor_codes(payload)
    assert payload["risk_level"] == RiskBand.CRITICAL.value


def test_no_gazette_match_does_not_create_conflict_factor() -> None:
    attempt = VerificationAttempt(
        case_id="case-1",
        adapter_name="kenya_law_gazette",
        status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
        query={"terms": ["LR 209/1234"]},
        evidence={"hits": []},
        message="No Gazette matches found.",
    )

    payload = analyze(attempts=[attempt])

    assert RiskFactorCode.GAZETTE_NOTICE_CONFLICT.value not in factor_codes(payload)
    assert payload["risk_level"] == RiskBand.LOW.value


def test_user_correction_replaces_bad_ai_value_for_scoring_without_mutating_ai_field() -> None:
    documents = make_core_documents()
    title = documents[0]
    parcel_field = next(field for field in title.extracted_fields if field.field_name == "parcel_number")
    parcel_field.value = "LR 209/9999"
    parcel_field.normalized_value = "LR 209/9999"
    title.field_corrections = [
        make_correction(document_id=title.id, field=parcel_field, corrected_value="LR 209/1234")
    ]

    payload = analyze(documents=documents)

    assert RiskFactorCode.PARCEL_NUMBER_MISMATCH.value not in factor_codes(payload)
    assert payload["risk_level"] == RiskBand.LOW.value
    assert parcel_field.value == "LR 209/9999"

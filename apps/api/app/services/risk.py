from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.domain.enums import DocumentCategory, RiskBand, RiskFactorCode, VerificationStatus
from app.models import Document, ExtractedField, FieldCorrection, LandCase, RiskAnalysisResult, RiskFactor, VerificationAttempt

RISK_ENGINE_VERSION = "mradi-risk-engine-v1.0.0"


@dataclass(frozen=True)
class RiskDefinition:
    label: str
    points: int
    severity: str
    recommendation: str


RISK_DEFINITIONS: dict[RiskFactorCode, RiskDefinition] = {
    RiskFactorCode.MISSING_TITLE_DEED: RiskDefinition(
        "No title deed uploaded",
        30,
        "critical",
        "Do not proceed until the seller provides a legible title deed for review.",
    ),
    RiskFactorCode.MISSING_PARCEL_OR_TITLE_NUMBER: RiskDefinition(
        "No parcel or title number extracted",
        30,
        "critical",
        "Ask for clearer documents and manually confirm the parcel or title number before signing.",
    ),
    RiskFactorCode.PARCEL_NUMBER_MISMATCH: RiskDefinition(
        "Parcel or title number mismatch",
        25,
        "critical",
        "Stop and reconcile parcel/title identifiers across the title deed, search, sale agreement, and survey documents.",
    ),
    RiskFactorCode.SELLER_NAME_MISMATCH: RiskDefinition(
        "Seller does not match official owner",
        30,
        "critical",
        "Ask a licensed advocate to confirm the registered owner before releasing money or signing.",
    ),
    RiskFactorCode.ID_MISMATCH: RiskDefinition(
        "ID number mismatch",
        15,
        "medium",
        "Confirm seller identity before signing or paying.",
    ),
    RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH: RiskDefinition(
        "Missing official land search",
        20,
        "high",
        "Obtain a fresh official land search before proceeding.",
    ),
    RiskFactorCode.STALE_SEARCH_CERTIFICATE: RiskDefinition(
        "Search certificate older than 30 days",
        15,
        "high",
        "Request a fresh official search certificate issued within the last 30 days.",
    ),
    RiskFactorCode.SALE_AGREEMENT_BEFORE_SEARCH: RiskDefinition(
        "Sale agreement predates search",
        15,
        "high",
        "Confirm no money changed hands before the official search and repeat due diligence.",
    ),
    RiskFactorCode.MISSING_CONSENT_TO_TRANSFER: RiskDefinition(
        "Missing consent to transfer",
        15,
        "high",
        "Confirm whether consent is required and obtain it before completion.",
    ),
    RiskFactorCode.MISSING_SPOUSAL_CONSENT: RiskDefinition(
        "Missing spousal consent",
        10,
        "medium",
        "Ask counsel whether spousal consent is required for this transaction.",
    ),
    RiskFactorCode.GAZETTE_NOTICE_CONFLICT: RiskDefinition(
        "Gazette conflict found",
        35,
        "critical",
        "Review the Gazette notice with an advocate before signing or paying.",
    ),
    RiskFactorCode.CAUTION_RESTRICTION_CHARGE: RiskDefinition(
        "Caution, restriction, charge, dispute, or encumbrance mentioned",
        30,
        "critical",
        "Resolve the encumbrance or restriction before signing.",
    ),
    RiskFactorCode.MULTIPLE_OWNERS_ONE_SELLER: RiskDefinition(
        "Multiple owners but only one seller signs",
        20,
        "high",
        "Confirm all registered owners have signed or lawfully authorized the transaction.",
    ),
    RiskFactorCode.POWER_OF_ATTORNEY_UNVERIFIED: RiskDefinition(
        "Power of attorney used but not fully supported",
        30,
        "critical",
        "Verify the power of attorney with the issuing registry and advocate before accepting signatures.",
    ),
    RiskFactorCode.POOR_IMAGE_QUALITY: RiskDefinition(
        "Uploaded document appears altered or unreadable",
        30,
        "critical",
        "Request clearer originals and have suspicious documents inspected by a professional.",
    ),
    RiskFactorCode.SUSPICIOUS_DOCUMENT_EDITS: RiskDefinition(
        "Suspicious edits or overwritten text",
        30,
        "critical",
        "Have originals inspected by an advocate or registry before relying on the document.",
    ),
    RiskFactorCode.LOW_DOCUMENT_CONFIDENCE: RiskDefinition(
        "Low document confidence",
        10,
        "medium",
        "Upload clearer scans or manually confirm the low-confidence fields.",
    ),
    RiskFactorCode.MISSING_KRA_PIN: RiskDefinition(
        "Missing KRA PIN",
        8,
        "medium",
        "Collect and verify the seller's KRA PIN certificate before completion.",
    ),
    RiskFactorCode.MISSING_WITNESS_OR_ADVOCATE_DETAILS: RiskDefinition(
        "Missing witness or advocate details",
        8,
        "medium",
        "Ask the parties to provide a properly witnessed or advocate-reviewed sale agreement.",
    ),
    RiskFactorCode.MISSING_RENT_OR_RATES_CLEARANCE: RiskDefinition(
        "Missing land rent or rates clearance",
        12,
        "high",
        "Obtain the relevant rent and rates clearance certificates before completion.",
    ),
    RiskFactorCode.BOUNDARY_OR_MUTATION_INCONSISTENCY: RiskDefinition(
        "Boundary, mutation, or survey inconsistency",
        18,
        "high",
        "Ask a licensed surveyor to compare the title, mutation form, and survey map.",
    ),
    RiskFactorCode.PAYMENT_BEFORE_VERIFICATION: RiskDefinition(
        "Buyer may pay before verification is complete",
        20,
        "high",
        "Do not release funds until verification is complete.",
    ),
    RiskFactorCode.DUPLICATE_PARCEL_NUMBER: RiskDefinition(
        "Parcel number appears in another case",
        14,
        "medium",
        "Check whether this is a duplicate review or possible double-sale pattern.",
    ),
}

CORE_REQUIRED_DOCUMENTS = {
    DocumentCategory.TITLE_DEED,
    DocumentCategory.SALE_AGREEMENT,
    DocumentCategory.NATIONAL_ID_OR_PASSPORT,
    DocumentCategory.KRA_PIN_CERTIFICATE,
    DocumentCategory.LAND_SEARCH_CERTIFICATE,
    DocumentCategory.CONSENT_TO_TRANSFER,
    DocumentCategory.RATES_CLEARANCE_CERTIFICATE,
    DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE,
}

KEY_PARCEL_DOCUMENTS = {
    DocumentCategory.TITLE_DEED,
    DocumentCategory.SALE_AGREEMENT,
    DocumentCategory.LAND_SEARCH_CERTIFICATE,
    DocumentCategory.MUTATION_FORM,
    DocumentCategory.SURVEY_MAP,
    DocumentCategory.KENYA_GAZETTE_NOTICE,
}

GAZETTE_CONFLICT_WORDS = (
    "acquisition",
    "compulsory acquisition",
    "revocation",
    "dispute",
    "public land",
    "road reserve",
    "restriction",
    "caution",
    "charge",
    "rectification",
)


def risk_band(score: int) -> RiskBand:
    if score <= 30:
        return RiskBand.LOW
    if score <= 60:
        return RiskBand.MEDIUM
    if score <= 80:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


def run_risk_analysis(
    *,
    case: LandCase,
    documents: list[Document],
    verification_attempts: list[VerificationAttempt],
    duplicate_case_ids: list[str] | None = None,
) -> tuple[RiskAnalysisResult, list[RiskFactor]]:
    payload = build_risk_analysis_payload(
        case=case,
        documents=documents,
        verification_attempts=verification_attempts,
        duplicate_case_ids=duplicate_case_ids or [],
    )
    result = RiskAnalysisResult(
        case_id=case.id,
        version=RISK_ENGINE_VERSION,
        score=payload["risk_score"],
        band=RiskBand(payload["risk_level"]),
        summary=payload["risk_summary"],
        input_snapshot=payload["input_snapshot"],
        result_json=payload,
    )
    factors = [
        RiskFactor(
            case_id=case.id,
            code=RiskFactorCode(factor["code"]),
            label=factor["label"],
            severity=factor["severity"],
            points=factor["points"],
            evidence={"evidence": factor["evidence"], "explanation": factor["explanation"]},
            recommendation=factor["recommendation"],
        )
        for factor in payload["risk_factors"]
    ]
    return result, factors


def build_risk_analysis_payload(
    *,
    case: LandCase,
    documents: list[Document],
    verification_attempts: list[VerificationAttempt],
    duplicate_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    duplicate_case_ids = duplicate_case_ids or []
    context = _RiskContext(case=case, documents=documents, verification_attempts=verification_attempts)
    factors: list[dict[str, Any]] = []
    missing_documents: list[dict[str, Any]] = []
    inconsistencies: list[dict[str, Any]] = []

    def add(
        code: RiskFactorCode,
        *,
        explanation: str,
        evidence: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if any(factor["code"] == code.value for factor in factors):
            return
        definition = RISK_DEFINITIONS[code]
        factors.append(
            {
                "code": code.value,
                "label": definition.label,
                "severity": definition.severity,
                "points": definition.points,
                "explanation": explanation,
                "recommendation": definition.recommendation,
                "evidence": evidence or [],
                **(extra or {}),
            }
        )

    categories = {document.category for document in documents}
    for category in sorted(CORE_REQUIRED_DOCUMENTS - categories, key=lambda item: item.value):
        severity = "critical" if category == DocumentCategory.TITLE_DEED else "high"
        if category in {DocumentCategory.NATIONAL_ID_OR_PASSPORT, DocumentCategory.KRA_PIN_CERTIFICATE}:
            severity = "medium"
        missing_documents.append(
            {
                "category": category.value,
                "severity": severity,
                "explanation": f"{category.value.replace('_', ' ')} was not uploaded.",
            }
        )

    if DocumentCategory.TITLE_DEED not in categories:
        add(
            RiskFactorCode.MISSING_TITLE_DEED,
            explanation="The title deed is a core ownership document and was not uploaded.",
        )
    if DocumentCategory.LAND_SEARCH_CERTIFICATE not in categories:
        add(
            RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH,
            explanation="No official land search certificate was uploaded for comparison.",
        )
    if DocumentCategory.CONSENT_TO_TRANSFER not in categories:
        add(
            RiskFactorCode.MISSING_CONSENT_TO_TRANSFER,
            explanation="Consent to transfer was not uploaded.",
        )
    if (
        DocumentCategory.RATES_CLEARANCE_CERTIFICATE not in categories
        or DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE not in categories
    ):
        add(
            RiskFactorCode.MISSING_RENT_OR_RATES_CLEARANCE,
            explanation="One or both rent/rates clearance certificates are missing.",
            extra={
                "rates_uploaded": DocumentCategory.RATES_CLEARANCE_CERTIFICATE in categories,
                "rent_uploaded": DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE in categories,
            },
        )
    if DocumentCategory.KRA_PIN_CERTIFICATE not in categories and not context.all_values("kra_pin"):
        add(RiskFactorCode.MISSING_KRA_PIN, explanation="No KRA PIN certificate or extracted KRA PIN was found.")

    parcel_values = context.values_by_category({"parcel_number"}, categories=KEY_PARCEL_DOCUMENTS)
    title_values = context.values_by_category({"title_number"}, categories=KEY_PARCEL_DOCUMENTS)
    if case.parcel_number_claimed:
        parcel_values.setdefault("case_input", []).append(
            _evidence(value=case.parcel_number_claimed, source="case_input", field_name="parcel_number")
        )
    unique_parcels = _unique_values(parcel_values)
    unique_titles = _unique_values(title_values)
    if not unique_parcels and not unique_titles:
        add(
            RiskFactorCode.MISSING_PARCEL_OR_TITLE_NUMBER,
            explanation="No parcel number or title number was extracted from the uploaded documents.",
        )
    elif len(unique_parcels) > 1 or len(unique_titles) > 1:
        evidence = [item for values in parcel_values.values() for item in values] + [
            item for values in title_values.values() for item in values
        ]
        inconsistencies.append(
            {
                "code": "parcel_title_mismatch",
                "severity": "critical",
                "parcel_values": sorted(unique_parcels),
                "title_values": sorted(unique_titles),
                "explanation": "Parcel or title identifiers do not match across key documents.",
            }
        )
        add(
            RiskFactorCode.PARCEL_NUMBER_MISMATCH,
            explanation="Parcel or title numbers differ across the case input and uploaded documents.",
            evidence=evidence,
        )

    search_owners = context.values_by_category({"owner_name"}, categories={DocumentCategory.LAND_SEARCH_CERTIFICATE})
    seller_names = context.values_by_category({"seller_name"}, categories={DocumentCategory.SALE_AGREEMENT, DocumentCategory.TITLE_DEED})
    if case.seller_name:
        seller_names.setdefault("case_input", []).append(_evidence(value=case.seller_name, source="case_input", field_name="seller_name"))
    owner_set = _unique_values(search_owners)
    seller_set = _unique_values(seller_names)
    if owner_set and seller_set:
        best_similarity = max(_name_similarity(owner, seller) for owner in owner_set for seller in seller_set)
        if best_similarity < 0.78:
            inconsistencies.append(
                {
                    "code": "seller_owner_mismatch",
                    "severity": "critical",
                    "owners": sorted(owner_set),
                    "sellers": sorted(seller_set),
                    "explanation": "Seller names do not match the owner names extracted from the search certificate.",
                }
            )
            add(
                RiskFactorCode.SELLER_NAME_MISMATCH,
                explanation="The seller name does not match the official search certificate owner.",
                evidence=[item for values in search_owners.values() for item in values]
                + [item for values in seller_names.values() for item in values],
            )
        elif best_similarity < 0.93:
            add(
                RiskFactorCode.SELLER_NAME_MISMATCH,
                explanation="Seller and owner names are similar but not exact; this may be a spelling mismatch.",
                evidence=[item for values in search_owners.values() for item in values]
                + [item for values in seller_names.values() for item in values],
                extra={"minor_mismatch": True},
            )

    id_values = _unique_values(context.values_by_category({"id_number"}))
    if len(id_values) > 1:
        add(
            RiskFactorCode.ID_MISMATCH,
            explanation="Different ID/passport numbers were extracted from uploaded documents.",
            evidence=[item for values in context.values_by_category({"id_number"}).values() for item in values],
        )

    search_dates = context.dates_for(DocumentCategory.LAND_SEARCH_CERTIFICATE)
    sale_dates = context.dates_for(DocumentCategory.SALE_AGREEMENT)
    if search_dates and max(search_dates) < date.today() - timedelta(days=30):
        add(
            RiskFactorCode.STALE_SEARCH_CERTIFICATE,
            explanation="The newest extracted search certificate date is older than 30 days.",
            extra={"search_dates": [item.isoformat() for item in search_dates]},
        )
    if search_dates and sale_dates and min(sale_dates) < min(search_dates):
        inconsistencies.append(
            {
                "code": "sale_before_search",
                "severity": "high",
                "sale_dates": [item.isoformat() for item in sale_dates],
                "search_dates": [item.isoformat() for item in search_dates],
                "explanation": "The sale agreement appears to have been signed before the search certificate date.",
            }
        )
        add(
            RiskFactorCode.SALE_AGREEMENT_BEFORE_SEARCH,
            explanation="Sale agreement date is earlier than the search certificate date.",
        )

    search_encumbrances = context.values_by_category(
        {"encumbrance_keyword"}, categories={DocumentCategory.LAND_SEARCH_CERTIFICATE}
    )
    if search_encumbrances:
        add(
            RiskFactorCode.CAUTION_RESTRICTION_CHARGE,
            explanation="The search certificate mentions caution, restriction, charge, dispute, or encumbrance terms.",
            evidence=[item for values in search_encumbrances.values() for item in values],
        )

    owner_count = len(owner_set)
    seller_count = len(seller_set)
    if owner_count > 1 and seller_count <= 1:
        add(
            RiskFactorCode.MULTIPLE_OWNERS_ONE_SELLER,
            explanation="Multiple owners were extracted but only one seller appears in the seller evidence.",
            evidence=[item for values in search_owners.values() for item in values],
        )
    if owner_count > 1 and DocumentCategory.SPOUSAL_CONSENT not in categories:
        add(
            RiskFactorCode.MISSING_SPOUSAL_CONSENT,
            explanation="Multiple registered owners or family-context clues suggest spousal consent may be needed.",
        )

    if DocumentCategory.POWER_OF_ATTORNEY in categories:
        poa_docs = [document for document in documents if document.category == DocumentCategory.POWER_OF_ATTORNEY]
        if any(
            not _document_has_field(
                document,
                {"document_date", "id_number", "signatures_present", "seals_present"},
            )
            for document in poa_docs
        ):
            add(
                RiskFactorCode.POWER_OF_ATTORNEY_UNVERIFIED,
                explanation="A power of attorney document was uploaded but key supporting details were not extracted.",
            )

    for document in documents:
        warnings = document.extraction_warnings or []
        if document.image_quality_score is not None and document.image_quality_score < 0.25:
            add(
                RiskFactorCode.POOR_IMAGE_QUALITY,
                explanation=f"{document.filename} is unreadable or too low quality for reliable extraction.",
                evidence=[_document_evidence(document, value=str(document.image_quality_score), field_name="image_quality_score")],
            )
        elif document.image_quality_score is not None and document.image_quality_score < 0.45:
            add(
                RiskFactorCode.LOW_DOCUMENT_CONFIDENCE,
                explanation=f"{document.filename} has low image/OCR confidence.",
                evidence=[_document_evidence(document, value=str(document.image_quality_score), field_name="image_quality_score")],
            )
        if any(warning.get("code") in {"poor_image_quality", "document_type_uncertain"} for warning in warnings):
            add(
                RiskFactorCode.LOW_DOCUMENT_CONFIDENCE,
                explanation=f"{document.filename} has extraction warnings that require user confirmation.",
                evidence=[_document_evidence(document, value=str(warnings), field_name="extraction_warnings")],
            )
        if context.values_for_document(document, {"visual_suspicion"}):
            add(
                RiskFactorCode.SUSPICIOUS_DOCUMENT_EDITS,
                explanation=f"{document.filename} contains suspicious edit or alteration signals.",
                evidence=context.values_for_document(document, {"visual_suspicion"}),
            )

    if DocumentCategory.SALE_AGREEMENT in categories:
        sale_docs = [document for document in documents if document.category == DocumentCategory.SALE_AGREEMENT]
        if any(not _document_has_field(document, {"signatures_present", "seals_present"}) for document in sale_docs):
            add(
                RiskFactorCode.MISSING_WITNESS_OR_ADVOCATE_DETAILS,
                explanation="The sale agreement does not show extracted witness, signature, seal, or advocate details.",
            )

    boundary_values = context.values_by_category(
        {"parcel_number", "block", "plot_number"},
        categories={DocumentCategory.MUTATION_FORM, DocumentCategory.SURVEY_MAP, DocumentCategory.TITLE_DEED},
    )
    boundary_mismatches = _field_mismatches(boundary_values)
    if boundary_mismatches:
        inconsistencies.append(
            {
                "code": "mutation_survey_title_inconsistency",
                "severity": "high",
                "explanation": "Mutation or survey identifiers do not align with the title deed.",
            }
        )
        add(
            RiskFactorCode.BOUNDARY_OR_MUTATION_INCONSISTENCY,
            explanation="Mutation/survey details are inconsistent with title deed details.",
            evidence=[item for values in boundary_values.values() for item in values],
        )

    if case.payment_before_verification:
        add(
            RiskFactorCode.PAYMENT_BEFORE_VERIFICATION,
            explanation="The buyer may release money before verification is complete.",
        )
    if duplicate_case_ids:
        add(
            RiskFactorCode.DUPLICATE_PARCEL_NUMBER,
            explanation="The parcel/title number appears in another case.",
            extra={"duplicate_case_ids": duplicate_case_ids},
        )

    gazette_evidence = _gazette_conflict_evidence(verification_attempts)
    if gazette_evidence:
        add(
            RiskFactorCode.GAZETTE_NOTICE_CONFLICT,
            explanation=(
                "Configured Gazette evidence contains acquisition, revocation, dispute, public land, "
                "road reserve, or compulsory acquisition signals."
            ),
            evidence=gazette_evidence,
        )

    raw_score = min(sum(factor["points"] for factor in factors), 100)
    critical_floor_applied = any(factor["severity"] == "critical" for factor in factors)
    score = max(raw_score, 81) if critical_floor_applied else raw_score
    score = min(score, 100)
    level = risk_band(score)
    evidence = [item for factor in factors for item in factor["evidence"]]
    summary = _risk_summary(score=score, level=level, factors=factors)
    return {
        "risk_score": score,
        "risk_level": level.value,
        "risk_summary": summary,
        "risk_factors": factors,
        "recommended_actions": _recommended_actions(factors),
        "missing_documents": missing_documents,
        "inconsistencies": inconsistencies,
        "evidence": evidence,
        "weight_table": _weight_table(),
        "scoring_version": RISK_ENGINE_VERSION,
        "critical_floor_applied": critical_floor_applied,
        "raw_score_before_critical_floor": raw_score,
        "input_snapshot": _input_snapshot(case, documents, verification_attempts),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def build_risk_factors(
    case: LandCase,
    documents: list[Document],
    verification_statuses: list[VerificationStatus],
    duplicate_case_ids: list[str] | None = None,
) -> tuple[int, RiskBand, list[RiskFactor]]:
    attempts = [
        VerificationAttempt(
            case_id=case.id,
            adapter_name="compatibility_status",
            status=status,
            query={},
            evidence={},
            message=status.value,
        )
        for status in verification_statuses
    ]
    result, factors = run_risk_analysis(
        case=case,
        documents=documents,
        verification_attempts=attempts,
        duplicate_case_ids=duplicate_case_ids,
    )
    return result.score, result.band, factors


class _RiskContext:
    def __init__(
        self,
        *,
        case: LandCase,
        documents: list[Document],
        verification_attempts: list[VerificationAttempt],
    ) -> None:
        self.case = case
        self.documents = documents
        self.verification_attempts = verification_attempts

    def all_values(self, field_name: str) -> list[dict[str, Any]]:
        return [item for values in self.values_by_category({field_name}).values() for item in values]

    def values_by_category(
        self,
        field_names: set[str],
        *,
        categories: set[DocumentCategory] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        values: dict[str, list[dict[str, Any]]] = {}
        for document in self.documents:
            if categories is not None and document.category not in categories:
                continue
            for item in self.values_for_document(document, field_names):
                values.setdefault(item["source_key"], []).append(item)
        return values

    def values_for_document(self, document: Document, field_names: set[str]) -> list[dict[str, Any]]:
        corrections_by_field_id = {
            correction.extracted_field_id: correction
            for correction in sorted(
                document.field_corrections or [],
                key=lambda item: item.created_at or datetime.min,
            )
            if correction.extracted_field_id
        }
        values: list[dict[str, Any]] = []
        for field in document.extracted_fields or []:
            if field.field_name not in field_names:
                continue
            correction = corrections_by_field_id.get(field.id)
            values.append(_field_evidence(document, field, correction))
        for correction in document.field_corrections or []:
            if correction.extracted_field_id or correction.field_name not in field_names:
                continue
            values.append(_correction_evidence(document, correction))
        return values

    def dates_for(self, category: DocumentCategory) -> list[date]:
        dates: list[date] = []
        for document in self.documents:
            if document.category != category:
                continue
            for item in self.values_for_document(document, {"document_date"}):
                try:
                    dates.append(datetime.fromisoformat(item["normalized_value"]).date())
                except ValueError:
                    continue
        return dates


def _field_evidence(
    document: Document, field: ExtractedField, correction: FieldCorrection | None = None
) -> dict[str, Any]:
    if correction is not None:
        return _correction_evidence(document, correction, ai_field=field)
    value = field.value
    normalized = (field.normalized_value or field.value).strip().upper()
    return {
        "document_id": document.id,
        "document_category": document.category.value,
        "field_name": field.field_name,
        "value": value,
        "normalized_value": normalized,
        "source": field.source,
        "source_key": f"{document.category.value}:{field.field_name}",
        "confidence": field.confidence,
        "page_number": field.page_number,
        "text_snippet": field.text_snippet,
    }


def _correction_evidence(
    document: Document,
    correction: FieldCorrection,
    ai_field: ExtractedField | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "document_category": document.category.value,
        "field_name": correction.field_name,
        "value": correction.corrected_value,
        "normalized_value": (correction.normalized_value or correction.corrected_value).strip().upper(),
        "source": "user_correction",
        "source_key": f"{document.category.value}:{correction.field_name}",
        "confidence": 1.0,
        "page_number": ai_field.page_number if ai_field else None,
        "text_snippet": correction.reason or (ai_field.text_snippet if ai_field else ""),
        "ai_value_preserved": correction.ai_value,
    }


def _evidence(
    *,
    value: str,
    source: str,
    field_name: str,
    normalized_value: str | None = None,
) -> dict[str, Any]:
    return {
        "document_id": None,
        "document_category": None,
        "field_name": field_name,
        "value": value,
        "normalized_value": (normalized_value or value).strip().upper(),
        "source": source,
        "source_key": source,
        "confidence": 1.0,
        "page_number": None,
        "text_snippet": "",
    }


def _document_evidence(document: Document, *, value: str, field_name: str) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "document_category": document.category.value,
        "field_name": field_name,
        "value": value,
        "normalized_value": value,
        "source": "document_metadata",
        "source_key": f"{document.category.value}:{field_name}",
        "confidence": document.image_quality_score,
        "page_number": None,
        "text_snippet": document.filename,
    }


def _unique_values(values: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {
        item["normalized_value"]
        for group in values.values()
        for item in group
        if item.get("normalized_value")
    }


def _field_mismatches(values: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    by_field: dict[str, set[str]] = {}
    for group in values.values():
        for item in group:
            if item.get("normalized_value"):
                by_field.setdefault(item["field_name"], set()).add(item["normalized_value"])
    return {field: sorted(field_values) for field, field_values in by_field.items() if len(field_values) > 1}


def _name_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _name_key(left), _name_key(right)).ratio()


def _name_key(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


def _document_has_field(document: Document, field_names: set[str]) -> bool:
    corrected_names = {correction.field_name for correction in document.field_corrections or []}
    ai_names = {field.field_name for field in document.extracted_fields or [] if field.value}
    return bool((corrected_names | ai_names) & field_names)


def _gazette_conflict_evidence(attempts: list[VerificationAttempt]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for attempt in attempts:
        if "gazette" not in attempt.adapter_name.lower():
            continue
        text = " ".join([attempt.message, str(attempt.evidence)]).lower()
        if attempt.status == VerificationStatus.CONFLICT_FOUND or any(word in text for word in GAZETTE_CONFLICT_WORDS):
            evidence.append(
                {
                    "document_id": None,
                    "document_category": "kenya_gazette_notice",
                    "field_name": "gazette_result",
                    "value": attempt.message or attempt.status.value,
                    "normalized_value": attempt.status.value.upper(),
                    "source": attempt.adapter_name,
                    "source_key": "gazette",
                    "confidence": 1.0,
                    "page_number": None,
                    "text_snippet": str(attempt.evidence)[:500],
                }
            )
    return evidence


def _recommended_actions(factors: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for factor in sorted(factors, key=lambda item: item["points"], reverse=True):
        recommendation = factor["recommendation"]
        if recommendation not in actions:
            actions.append(recommendation)
    if not actions:
        actions.append("Proceed only after a licensed advocate confirms the official registry search.")
    return actions


def _risk_summary(*, score: int, level: RiskBand, factors: list[dict[str, Any]]) -> str:
    if not factors:
        return (
            "Low risk: key uploaded documents are internally consistent, no Gazette conflict was found, "
            "and no encumbrance was extracted."
        )
    top = sorted(factors, key=lambda item: item["points"], reverse=True)[:3]
    labels = ", ".join(item["label"].lower() for item in top)
    return f"{level.value.title()} risk: score {score}/100 based on {len(factors)} factor(s), led by {labels}."


def _weight_table() -> list[dict[str, Any]]:
    return [
        {
            "code": code.value,
            "label": definition.label,
            "points": definition.points,
            "severity": definition.severity,
        }
        for code, definition in RISK_DEFINITIONS.items()
    ]


def _input_snapshot(
    case: LandCase,
    documents: list[Document],
    verification_attempts: list[VerificationAttempt],
) -> dict[str, Any]:
    return {
        "case": {
            "id": case.id,
            "seller_name": case.seller_name,
            "buyer_name": case.buyer_name,
            "parcel_number_claimed": case.parcel_number_claimed,
            "payment_before_verification": case.payment_before_verification,
        },
        "documents": [
            {
                "id": document.id,
                "category": document.category.value,
                "status": document.status.value,
                "image_quality_score": document.image_quality_score,
                "extracted_field_count": len(document.extracted_fields or []),
                "correction_count": len(document.field_corrections or []),
            }
            for document in documents
        ],
        "verification_attempts": [
            {
                "adapter_name": attempt.adapter_name,
                "status": attempt.status.value,
                "message": attempt.message,
            }
            for attempt in verification_attempts
        ],
    }

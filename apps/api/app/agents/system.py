from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from app.adapters.gazette import KenyaGazetteAdapter
from app.adapters.verification import VerificationResult
from app.agents.contracts import (
    AgentDecision,
    AgentFailure,
    AgentRiskFactor,
    CaseProfile,
    ConsistencyAgentInput,
    ConsistencyAgentOutput,
    DateSequenceFinding,
    DocumentDescriptor,
    EvidenceReference,
    ExtractedDocumentFields,
    FieldMismatch,
    GazetteAgentStatus,
    GazetteNotice,
    GazetteSearchAgentInput,
    GazetteSearchAgentOutput,
    IntakeAgentInput,
    IntakeAgentOutput,
    LegalSafetyAgentInput,
    LegalSafetyAgentOutput,
    MissingDocumentFinding,
    OfficialSearchAgentInput,
    OfficialSearchAgentOutput,
    ParsedOfficialSearchCertificate,
    ReportAgentInput,
    ReportAgentOutput,
    RiskScoringAgentInput,
    RiskScoringAgentOutput,
    VisionExtractionAgentInput,
    VisionExtractionAgentOutput,
)
from app.domain.enums import DocumentCategory, RiskFactorCode, VerificationStatus
from app.services.extraction import FieldExtraction, extract_document_fields
from app.services.reporting import LEGAL_DISCLAIMER, build_report_content
from app.services.risk import RISK_DEFINITIONS, risk_band
from app.services.storage import StorageProvider

CORE_REQUIRED_DOCUMENTS = [
    DocumentCategory.TITLE_DEED,
    DocumentCategory.SALE_AGREEMENT,
    DocumentCategory.NATIONAL_ID_OR_PASSPORT,
    DocumentCategory.KRA_PIN_CERTIFICATE,
    DocumentCategory.LAND_SEARCH_CERTIFICATE,
    DocumentCategory.CONSENT_TO_TRANSFER,
    DocumentCategory.RATES_CLEARANCE_CERTIFICATE,
    DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE,
]


class IntakeAgent:
    name = "IntakeAgent"

    def run(self, payload: IntakeAgentInput) -> IntakeAgentOutput:
        missing_inputs = [
            field
            for field, value in {
                "buyer_name": payload.buyer_name,
                "seller_name": payload.seller_name,
                "parcel_number_claimed": payload.parcel_number_claimed,
                "location_county": payload.location_county,
            }.items()
            if not value.strip()
        ]
        uploaded_categories = sorted(
            {document.category for document in payload.documents},
            key=lambda category: category.value,
        )
        profile = CaseProfile(
            case_id=payload.case_id,
            title=payload.title,
            buyer_name=payload.buyer_name.strip(),
            seller_name=payload.seller_name.strip(),
            parcel_number_claimed=payload.parcel_number_claimed.strip(),
            county=payload.location_county.strip(),
            preferred_language=payload.preferred_language,
            payment_before_verification=payload.payment_before_verification,
            missing_inputs=missing_inputs,
            uploaded_document_categories=uploaded_categories,
            required_document_categories=CORE_REQUIRED_DOCUMENTS,
        )
        confidence = 0.95 if not missing_inputs else 0.68
        return IntakeAgentOutput(
            case_profile=profile,
            confidence=confidence,
            decisions=[
                AgentDecision(
                    decision="case_profile_created",
                    reason=(
                        "Required transaction inputs are present."
                        if not missing_inputs
                        else f"Missing transaction inputs: {', '.join(missing_inputs)}."
                    ),
                    confidence=confidence,
                )
            ],
        )


class VisionExtractionAgent:
    name = "VisionExtractionAgent"

    def __init__(self, storage: StorageProvider):
        self.storage = storage

    async def run(self, payload: VisionExtractionAgentInput) -> VisionExtractionAgentOutput:
        extracted_documents: list[ExtractedDocumentFields] = []
        tool_statuses: dict[str, str] = {}
        decisions: list[AgentDecision] = []
        for document in payload.documents:
            try:
                content = self.storage.read_bytes(document.storage_uri)
                fields, quality, verification_status, text = extract_document_fields(
                    content=content,
                    content_type=document.content_type,
                    category=document.category,
                )
                tool_statuses[document.id] = verification_status.value
                extracted = _fields_to_document(document, fields, quality)
                extracted_documents.append(extracted)
                decisions.append(
                    AgentDecision(
                        decision="document_extracted" if fields else "manual_review_required",
                        reason=(
                            f"Extracted {len(fields)} structured fields from {document.filename}."
                            if fields
                            else f"No reliable text was extracted from {document.filename}; manual review is required."
                        ),
                        confidence=extracted.extraction_confidence,
                        evidence=extracted.evidence[:5],
                    )
                )
                if text and not fields:
                    tool_statuses[f"{document.id}:native_text"] = "text_found_no_structured_fields"
            except Exception as exc:
                tool_statuses[document.id] = "failed"
                extracted_documents.append(
                    ExtractedDocumentFields(
                        document_id=document.id,
                        category=document.category,
                        filename=document.filename,
                        document_type=document.category.value,
                        extraction_confidence=0.0,
                        failure=AgentFailure(
                            code="document_extraction_failed",
                            message=str(exc),
                            retryable=True,
                        ),
                    )
                )
                decisions.append(
                    AgentDecision(
                        decision="document_extraction_failed",
                        reason=f"Extraction failed for {document.filename}: {exc}",
                        confidence=0.0,
                    )
                )
        confidence = _mean([document.extraction_confidence for document in extracted_documents])
        return VisionExtractionAgentOutput(
            documents=extracted_documents,
            tool_statuses=tool_statuses,
            confidence=confidence,
            decisions=decisions,
        )


class ConsistencyAgent:
    name = "ConsistencyAgent"

    def run(self, payload: ConsistencyAgentInput) -> ConsistencyAgentOutput:
        documents = payload.extracted_documents
        categories = {document.category for document in documents}
        missing = [
            MissingDocumentFinding(
                category=category,
                explanation=f"{category.value.replace('_', ' ')} is part of the core due-diligence packet.",
                severity="high" if category == DocumentCategory.LAND_SEARCH_CERTIFICATE else "medium",
            )
            for category in CORE_REQUIRED_DOCUMENTS
            if category not in categories
        ]
        mismatches: list[FieldMismatch] = []
        mismatches.extend(_mismatch_for("parcel_number_mismatch", "Parcel number mismatch", _values_with_refs(documents, "parcel_number")))
        mismatches.extend(_mismatch_for("title_number_mismatch", "Title number mismatch", _values_with_refs(documents, "title_number")))
        mismatches.extend(_seller_owner_mismatch(documents, payload.case_profile))
        mismatches.extend(_mismatch_for("id_mismatch", "ID number mismatch", _values_with_refs(documents, "id_numbers")))

        date_findings = _date_findings(documents)
        old_search = any(finding.code == "stale_search_certificate" for finding in date_findings)
        mutation_inconsistency = (
            DocumentCategory.MUTATION_FORM in categories and DocumentCategory.SURVEY_MAP not in categories
        )
        if mutation_inconsistency:
            mismatches.append(
                FieldMismatch(
                    code="boundary_or_mutation_inconsistency",
                    label="Mutation form uploaded without survey map",
                    severity="medium",
                    explanation="Mutation and survey map evidence should be reviewed together to confirm boundaries.",
                    evidence=[
                        EvidenceReference(
                            document_id=document.document_id,
                            document_category=document.category,
                            source="uploaded_document",
                            confidence=document.extraction_confidence,
                        )
                        for document in documents
                        if document.category == DocumentCategory.MUTATION_FORM
                    ],
                )
            )
        confidence = 0.92 if not mismatches and not missing and not date_findings else 0.78
        return ConsistencyAgentOutput(
            missing_required_documents=missing,
            mismatches=mismatches,
            suspicious_date_sequences=date_findings,
            old_search_certificate=old_search,
            mutation_survey_inconsistency=mutation_inconsistency,
            confidence=confidence,
            decisions=[
                AgentDecision(
                    decision="consistency_review_completed",
                    reason=(
                        f"Found {len(mismatches)} mismatch groups, {len(missing)} missing document groups, "
                        f"and {len(date_findings)} date warnings."
                    ),
                    confidence=confidence,
                    evidence=[ref for mismatch in mismatches for ref in mismatch.evidence][:8],
                )
            ],
        )


class GazetteSearchAgent:
    name = "GazetteSearchAgent"

    def __init__(self, adapter: KenyaGazetteAdapter | None = None):
        self.adapter = adapter or KenyaGazetteAdapter()

    async def run(self, payload: GazetteSearchAgentInput) -> GazetteSearchAgentOutput:
        query_terms = _gazette_query_terms(payload.case_profile, payload.extracted_documents)
        if not query_terms:
            return GazetteSearchAgentOutput(
                gazette_status="not_checked",
                reason=(
                    "No parcel number, title number, registry, county, owner name, or land reference number "
                    "was available for Gazette search."
                ),
                confidence=1.0,
                decisions=[
                    AgentDecision(
                        decision="gazette_not_checked",
                        reason="No usable Gazette query terms were available.",
                        confidence=1.0,
                    )
                ],
            )
        try:
            result = await _search_gazette_adapter(self.adapter, query_terms)
        except Exception as exc:
            return GazetteSearchAgentOutput(
                status="failed",
                gazette_status="not_checked",
                query_terms=query_terms,
                reason=f"Gazette search failed transparently: {exc}",
                confidence=0.0,
                failure=AgentFailure(code="gazette_adapter_failed", message=str(exc), retryable=True),
            )
        if result.status == VerificationStatus.ADAPTER_UNAVAILABLE or result.status == VerificationStatus.NOT_CHECKED:
            return GazetteSearchAgentOutput(
                gazette_status="not_checked",
                query_terms=query_terms,
                reason=result.message or "Gazette search was not checked because the configured adapter was unavailable.",
                confidence=0.0,
                decisions=[
                    AgentDecision(
                        decision="gazette_not_checked",
                        reason=result.message or "Adapter unavailable.",
                        confidence=0.0,
                    )
                ],
            )
        notices = [
            GazetteNotice(
                source=result.adapter_name,
                date=str(hit.get("date", "")),
                title=str(hit.get("title", "Kenya Gazette mention")),
                url=str(hit.get("url", "")),
                snippet=str(hit.get("snippet", "")),
                confidence=float(hit.get("confidence", 0.7)),
            )
            for hit in result.evidence.get("hits", [])
            if isinstance(hit, dict)
        ]
        status: GazetteAgentStatus = "matches_found" if notices else "checked_no_match"
        return GazetteSearchAgentOutput(
            gazette_status=status,
            query_terms=query_terms,
            notices=notices,
            reason=result.message,
            confidence=0.72 if notices else 0.84,
            decisions=[
                AgentDecision(
                    decision="gazette_matches_found" if notices else "gazette_checked_no_match",
                    reason=result.message,
                    confidence=0.72 if notices else 0.84,
                )
            ],
        )


class OfficialSearchAgent:
    name = "OfficialSearchAgent"

    def run(self, payload: OfficialSearchAgentInput) -> OfficialSearchAgentOutput:
        search_documents = [
            document for document in payload.extracted_documents if document.category == DocumentCategory.LAND_SEARCH_CERTIFICATE
        ]
        if not search_documents:
            return OfficialSearchAgentOutput(
                official_search_status="missing",
                verification_status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                reason="No official land search certificate was uploaded. The case is incomplete and ownership is not officially verified.",
                confidence=1.0,
                decisions=[
                    AgentDecision(
                        decision="official_search_missing",
                        reason="No land search certificate exists in the uploaded document set.",
                        confidence=1.0,
                    )
                ],
            )
        certificate_doc = search_documents[0]
        date_candidates = certificate_doc.search_dates or certificate_doc.document_dates
        certificate = ParsedOfficialSearchCertificate(
            document_id=certificate_doc.document_id,
            owner_names=certificate_doc.owner_names,
            parcel_number=certificate_doc.parcel_number,
            title_number=certificate_doc.title_number,
            encumbrances=[
                *certificate_doc.encumbrances,
                *certificate_doc.cautions,
                *certificate_doc.restrictions,
                *certificate_doc.charges,
            ],
            date_issued=date_candidates[0] if date_candidates else None,
            evidence=certificate_doc.evidence,
        )
        conflicts = _official_search_conflicts(certificate, payload.extracted_documents)
        status = VerificationStatus.CONFLICT_FOUND if conflicts else VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE
        return OfficialSearchAgentOutput(
            official_search_status="parsed",
            verification_status=status,
            certificate=certificate,
            conflicts=conflicts,
            reason=(
                "Uploaded official search certificate was parsed, but no independent registry API verification was performed."
                if not conflicts
                else "Uploaded official search certificate conflicts with other uploaded documents."
            ),
            confidence=0.78 if not conflicts else 0.62,
            decisions=[
                AgentDecision(
                    decision="official_search_parsed",
                    reason="The uploaded search certificate was parsed; official registry ownership verification is still not claimed.",
                    confidence=0.78,
                    evidence=certificate.evidence[:6],
                )
            ],
        )


class RiskScoringAgent:
    name = "RiskScoringAgent"

    def run(self, payload: RiskScoringAgentInput) -> RiskScoringAgentOutput:
        factors: list[AgentRiskFactor] = []

        def add(code: RiskFactorCode, evidence: dict[str, Any], evidence_refs: list[EvidenceReference] | None = None) -> None:
            if any(factor.code == code for factor in factors):
                return
            definition = RISK_DEFINITIONS[code]
            factors.append(
                AgentRiskFactor(
                    code=code,
                    label=definition.label,
                    severity=definition.severity,
                    points=definition.points,
                    evidence=evidence,
                    evidence_refs=evidence_refs or [],
                    recommendation=definition.recommendation,
                )
            )

        mismatch_code_map = {
            "parcel_number_mismatch": RiskFactorCode.PARCEL_NUMBER_MISMATCH,
            "title_number_mismatch": RiskFactorCode.PARCEL_NUMBER_MISMATCH,
            "seller_name_mismatch": RiskFactorCode.SELLER_NAME_MISMATCH,
            "id_mismatch": RiskFactorCode.ID_MISMATCH,
            "boundary_or_mutation_inconsistency": RiskFactorCode.BOUNDARY_OR_MUTATION_INCONSISTENCY,
        }
        for mismatch in payload.consistency.mismatches:
            if mismatch.code in mismatch_code_map:
                add(mismatch_code_map[mismatch.code], {"values": mismatch.values, "explanation": mismatch.explanation}, mismatch.evidence)
        missing_categories = {finding.category for finding in payload.consistency.missing_required_documents}
        if DocumentCategory.TITLE_DEED in missing_categories:
            add(RiskFactorCode.MISSING_TITLE_DEED, {"required_document": "title_deed"})
        if DocumentCategory.LAND_SEARCH_CERTIFICATE in missing_categories or payload.official_search.official_search_status == "missing":
            add(RiskFactorCode.MISSING_OFFICIAL_LAND_SEARCH, {"required_document": "land_search_certificate"})
        if DocumentCategory.CONSENT_TO_TRANSFER in missing_categories:
            add(RiskFactorCode.MISSING_CONSENT_TO_TRANSFER, {"required_document": "consent_to_transfer"})
        if DocumentCategory.KRA_PIN_CERTIFICATE in missing_categories and not any(
            document.kra_pin for document in payload.extracted_documents
        ):
            add(RiskFactorCode.MISSING_KRA_PIN, {"required_document": "kra_pin_certificate"})
        if (
            DocumentCategory.RATES_CLEARANCE_CERTIFICATE in missing_categories
            or DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE in missing_categories
        ):
            add(
                RiskFactorCode.MISSING_RENT_OR_RATES_CLEARANCE,
                {
                    "rates_uploaded": DocumentCategory.RATES_CLEARANCE_CERTIFICATE not in missing_categories,
                    "rent_uploaded": DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE not in missing_categories,
                },
            )
        for finding in payload.consistency.suspicious_date_sequences:
            if finding.code == "stale_search_certificate":
                add(RiskFactorCode.STALE_SEARCH_CERTIFICATE, {"dates": _json_safe(finding.dates)}, finding.evidence)
            if finding.code == "sale_agreement_before_search":
                add(RiskFactorCode.SALE_AGREEMENT_BEFORE_SEARCH, {"dates": _json_safe(finding.dates)}, finding.evidence)
        for document in payload.extracted_documents:
            if document.document_quality_score is not None and document.document_quality_score < 0.45:
                add(
                    RiskFactorCode.POOR_IMAGE_QUALITY,
                    {"document_id": document.document_id, "quality_score": document.document_quality_score},
                    [
                        EvidenceReference(
                            document_id=document.document_id,
                            document_category=document.category,
                            confidence=document.document_quality_score,
                        )
                    ],
                )
            if document.suspicious_edit_signals:
                add(
                    RiskFactorCode.SUSPICIOUS_DOCUMENT_EDITS,
                    {"signals": document.suspicious_edit_signals},
                    document.evidence,
                )
            if document.encumbrances or document.cautions or document.restrictions or document.charges:
                add(
                    RiskFactorCode.CAUTION_RESTRICTION_CHARGE,
                    {
                        "encumbrances": document.encumbrances,
                        "cautions": document.cautions,
                        "restrictions": document.restrictions,
                        "charges": document.charges,
                    },
                    document.evidence,
                )
        owner_values = {
            _norm(owner_name)
            for document in payload.extracted_documents
            for owner_name in document.owner_names
            if owner_name.strip()
        }
        seller_values = {
            _norm(seller_name)
            for document in payload.extracted_documents
            for seller_name in document.seller_names
            if seller_name.strip()
        }
        if payload.case_profile.seller_name.strip():
            seller_values.add(_norm(payload.case_profile.seller_name))
        if len(owner_values) > 1 and len(seller_values) <= 1:
            add(
                RiskFactorCode.MULTIPLE_OWNERS_ONE_SELLER,
                {"owner_count": len(owner_values), "seller_count": len(seller_values)},
            )
        if len(owner_values) > 1 and DocumentCategory.SPOUSAL_CONSENT not in payload.case_profile.uploaded_document_categories:
            add(RiskFactorCode.MISSING_SPOUSAL_CONSENT, {"required_document": "spousal_consent"})
        if DocumentCategory.POWER_OF_ATTORNEY in payload.case_profile.uploaded_document_categories:
            add(RiskFactorCode.POWER_OF_ATTORNEY_UNVERIFIED, {"status": "requires independent verification"})
        if payload.gazette.gazette_status == "matches_found":
            conflict_words = ("lost title", "revocation", "caution", "restriction", "rectification", "charge")
            if any(any(word in notice.snippet.lower() for word in conflict_words) for notice in payload.gazette.notices):
                add(
                    RiskFactorCode.GAZETTE_NOTICE_CONFLICT,
                    {"notices": [notice.model_dump() for notice in payload.gazette.notices]},
                )
        if payload.official_search.verification_status == VerificationStatus.CONFLICT_FOUND:
            add(
                RiskFactorCode.PARCEL_NUMBER_MISMATCH,
                {"official_search_conflicts": [conflict.model_dump(mode="json") for conflict in payload.official_search.conflicts]},
                [ref for conflict in payload.official_search.conflicts for ref in conflict.evidence],
            )
        if payload.case_profile.payment_before_verification:
            add(RiskFactorCode.PAYMENT_BEFORE_VERIFICATION, {"case_flag": True})
        if payload.duplicate_case_ids:
            add(RiskFactorCode.DUPLICATE_PARCEL_NUMBER, {"case_ids": payload.duplicate_case_ids})

        raw_score = min(sum(factor.points for factor in factors), 100)
        score = max(raw_score, 81) if any(factor.severity == "critical" for factor in factors) else raw_score
        score = min(score, 100)
        band = risk_band(score)
        return RiskScoringAgentOutput(
            score=score,
            risk_level=band,
            risk_factors=factors,
            recommended_next_actions=_recommended_actions(factors),
            confidence=0.9,
            decisions=[
                AgentDecision(
                    decision="risk_score_calculated",
                    reason=f"Calculated {score}/100 {band.value} risk from {len(factors)} transparent factors.",
                    confidence=0.9,
                    evidence=[ref for factor in factors for ref in factor.evidence_refs][:10],
                )
            ],
        )


class ReportAgent:
    name = "ReportAgent"

    def run(self, payload: ReportAgentInput) -> ReportAgentOutput:
        content = build_report_content(
            case=_case_like(payload.case_profile),
            score=payload.risk.score,
            band=payload.risk.risk_level,
            verification_status=payload.verification_status,
            factors=[],
            language=payload.case_profile.preferred_language,
            agent_context={
                "document_checklist": [
                    {
                        "category": category.value,
                        "uploaded": category in payload.case_profile.uploaded_document_categories,
                    }
                    for category in payload.case_profile.required_document_categories
                ],
                "extracted_documents": [document.model_dump(mode="json") for document in payload.extracted_documents],
                "missing_documents": [finding.model_dump(mode="json") for finding in payload.consistency.missing_required_documents],
                "inconsistencies": payload.consistency.model_dump(mode="json"),
                "gazette_results": payload.gazette.model_dump(mode="json"),
                "official_search": payload.official_search.model_dump(mode="json"),
                "recommended_next_actions": payload.risk.recommended_next_actions,
                "risk_factors": [factor.model_dump(mode="json") for factor in payload.risk.risk_factors],
            },
        )
        return ReportAgentOutput(
            content=content,
            generated_at=datetime.now(UTC),
            confidence=0.88,
            decisions=[
                AgentDecision(
                    decision="buyer_report_generated",
                    reason=(
                        "Generated a buyer-friendly report with checklist, extracted fields, inconsistencies, "
                        "Gazette results, score, next steps, and disclaimer."
                    ),
                    confidence=0.88,
                )
            ],
        )


class LegalSafetyAgent:
    name = "LegalSafetyAgent"

    def run(self, payload: LegalSafetyAgentInput) -> LegalSafetyAgentOutput:
        content = dict(payload.report_content)
        blocked_claims: list[str] = []
        text = str(content).lower()
        unsafe_claims = [
            "officially verified ownership",
            "ownership verified",
            "guaranteed safe",
            "safe to buy",
        ]
        if payload.verification_status != VerificationStatus.VERIFIED:
            for claim in unsafe_claims:
                if claim in text:
                    blocked_claims.append(claim)
            if blocked_claims:
                summary = content.setdefault("summary", {})
                if isinstance(summary, dict):
                    summary["plain_english"] = (
                        f"{summary.get('plain_english', '')} Ownership has not been independently verified from an official registry API."
                    ).strip()
        content["legal_disclaimer"] = LEGAL_DISCLAIMER
        approved = not blocked_claims
        return LegalSafetyAgentOutput(
            approved=approved,
            disclaimer=LEGAL_DISCLAIMER,
            blocked_claims=blocked_claims,
            sanitized_content=content,
            confidence=0.96,
            decisions=[
                AgentDecision(
                    decision="legal_safety_checked",
                    reason=(
                        "No unsafe ownership verification claims were found."
                        if approved
                        else f"Blocked unsafe claims: {', '.join(blocked_claims)}."
                    ),
                    confidence=0.96,
                )
            ],
        )


def _fields_to_document(
    document: DocumentDescriptor,
    fields: list[FieldExtraction],
    quality: float | None,
) -> ExtractedDocumentFields:
    grouped: dict[str, list[FieldExtraction]] = defaultdict(list)
    for field in fields:
        grouped[field.field_name].append(field)

    def first(name: str) -> str:
        return grouped[name][0].value if grouped.get(name) else ""

    def values(name: str) -> list[str]:
        return [field.value for field in grouped.get(name, []) if field.value]

    def dates(name: str = "document_date") -> list[date]:
        parsed: list[date] = []
        for field in grouped.get(name, []):
            try:
                parsed.append(date.fromisoformat(field.normalized_value))
            except ValueError:
                continue
        return parsed

    evidence = [
        EvidenceReference(
            document_id=document.id,
            document_category=document.category,
            field_name=field.field_name,
            quote=field.value[:240],
            source=field.source,
            confidence=field.confidence,
            page_number=field.page_number,
            bounding_box=field.bounding_box,
            text_snippet=field.text_snippet,
            metadata=field.metadata or {},
        )
        for field in fields
    ]
    field_confidence = _mean([field.confidence for field in fields])
    confidence = round((field_confidence * 0.75) + ((quality or 0.0) * 0.25), 2) if fields else 0.0
    document_dates = dates()
    return ExtractedDocumentFields(
        document_id=document.id,
        category=document.category,
        filename=document.filename,
        document_type=document.category.value,
        parcel_number=first("parcel_number"),
        title_number=first("title_number"),
        registry=first("registry"),
        county=first("county"),
        block=first("block"),
        plot_number=first("plot_number"),
        owner_names=values("owner_name"),
        seller_names=values("seller_name"),
        buyer_names=values("buyer_name"),
        id_numbers=values("id_number"),
        kra_pin=first("kra_pin"),
        document_dates=document_dates,
        transfer_dates=document_dates if document.category == DocumentCategory.CONSENT_TO_TRANSFER else [],
        search_dates=document_dates if document.category == DocumentCategory.LAND_SEARCH_CERTIFICATE else [],
        land_size=first("land_size"),
        encumbrances=values("encumbrance_keyword"),
        cautions=[value for value in values("encumbrance_keyword") if value.lower() == "caution"],
        restrictions=[value for value in values("encumbrance_keyword") if value.lower() == "restriction"],
        charges=[value for value in values("encumbrance_keyword") if value.lower() == "charge"],
        signatures_present=_bool_field(first("signatures_present")),
        seals_present=_bool_field(first("seals_present")),
        suspicious_edit_signals=values("visual_suspicion"),
        document_quality_score=quality,
        extraction_confidence=confidence,
        extraction_sources=sorted({field.source for field in fields}),
        evidence=evidence,
    )


def _mismatch_for(code: str, label: str, values: dict[str, list[EvidenceReference]]) -> list[FieldMismatch]:
    normalized_values = sorted(value for value in values if value)
    if len(normalized_values) <= 1:
        return []
    return [
        FieldMismatch(
            code=code,
            label=label,
            severity="high" if "parcel" in code or "title" in code else "medium",
            values=normalized_values,
            explanation=f"Multiple different {label.lower()} values were found across uploaded documents.",
            evidence=[ref for refs in values.values() for ref in refs],
        )
    ]


def _seller_owner_mismatch(documents: list[ExtractedDocumentFields], case_profile: CaseProfile) -> list[FieldMismatch]:
    values: dict[str, list[EvidenceReference]] = defaultdict(list)
    if case_profile.seller_name:
        values[_norm(case_profile.seller_name)].append(
            EvidenceReference(source="case_input", quote=case_profile.seller_name, confidence=0.9)
        )
    for document in documents:
        for field_name, names in (("seller_name", document.seller_names), ("owner_name", document.owner_names)):
            for name in names:
                values[_norm(name)].extend(
                    [ref for ref in document.evidence if ref.field_name == field_name and _norm(ref.quote) == _norm(name)]
                    or [
                        EvidenceReference(
                            document_id=document.document_id,
                            document_category=document.category,
                            field_name=field_name,
                            quote=name,
                            confidence=document.extraction_confidence,
                        )
                    ]
                )
    if len([value for value in values if value]) <= 1:
        return []
    return [
        FieldMismatch(
            code="seller_name_mismatch",
            label="Seller or owner name mismatch",
            severity="high",
            values=sorted(values),
            explanation="The seller named in the case does not consistently match owner or seller names extracted from uploaded documents.",
            evidence=[ref for refs in values.values() for ref in refs],
        )
    ]


def _values_with_refs(documents: list[ExtractedDocumentFields], attr: str) -> dict[str, list[EvidenceReference]]:
    values: dict[str, list[EvidenceReference]] = defaultdict(list)
    field_names = [attr]
    if attr == "id_numbers":
        field_names = ["id_number"]
    for document in documents:
        raw_values = getattr(document, attr)
        if isinstance(raw_values, str):
            raw_values = [raw_values] if raw_values else []
        for value in raw_values:
            refs = [
                ref for ref in document.evidence if ref.field_name in field_names and _norm(ref.quote) == _norm(str(value))
            ]
            values[_norm(str(value))].extend(
                refs
                or [
                    EvidenceReference(
                        document_id=document.document_id,
                        document_category=document.category,
                        field_name=field_names[0],
                        quote=str(value),
                        confidence=document.extraction_confidence,
                    )
                ]
            )
    return values


def _date_findings(documents: list[ExtractedDocumentFields]) -> list[DateSequenceFinding]:
    findings: list[DateSequenceFinding] = []
    search_dates = [day for document in documents for day in document.search_dates]
    sale_dates = [
        day
        for document in documents
        if document.category == DocumentCategory.SALE_AGREEMENT
        for day in document.document_dates
    ]
    if search_dates and min(search_dates) < date.today() - timedelta(days=30):
        findings.append(
            DateSequenceFinding(
                code="stale_search_certificate",
                explanation="The uploaded official search certificate appears older than 30 days.",
                dates={"search_dates": search_dates},
                evidence=[
                    ref
                    for document in documents
                    if document.category == DocumentCategory.LAND_SEARCH_CERTIFICATE
                    for ref in document.evidence
                    if ref.field_name == "document_date"
                ],
            )
        )
    if search_dates and sale_dates and min(sale_dates) < min(search_dates):
        findings.append(
            DateSequenceFinding(
                code="sale_agreement_before_search",
                explanation="The sale agreement date appears earlier than the search certificate date.",
                dates={"sale_dates": sale_dates, "search_dates": search_dates},
                evidence=[
                    ref
                    for document in documents
                    for ref in document.evidence
                    if ref.field_name == "document_date"
                ],
            )
        )
    return findings


def _gazette_query_terms(profile: CaseProfile, documents: list[ExtractedDocumentFields]) -> list[str]:
    terms = [
        profile.parcel_number_claimed,
        profile.county,
    ]
    for document in documents:
        terms.extend(
            [
                document.parcel_number,
                document.title_number,
                document.registry,
                document.county,
                *document.owner_names,
            ]
        )
    seen: set[str] = set()
    output: list[str] = []
    for term in terms:
        normalized = re.sub(r"\s+", " ", term or "").strip()
        if normalized and normalized.upper() not in seen:
            seen.add(normalized.upper())
            output.append(normalized)
    return output


async def _search_gazette_adapter(adapter: Any, query_terms: list[str]) -> VerificationResult:
    if hasattr(adapter, "search_terms"):
        return cast(VerificationResult, await adapter.search_terms(query_terms))
    for term in query_terms:
        result = await adapter.search(term)
        if result.evidence.get("hits") or result.status in {
            VerificationStatus.CONFLICT_FOUND,
            VerificationStatus.ADAPTER_UNAVAILABLE,
            VerificationStatus.NOT_CHECKED,
        }:
            return cast(VerificationResult, result)
    return cast(VerificationResult, await adapter.search(query_terms[0]))


def _official_search_conflicts(
    certificate: ParsedOfficialSearchCertificate,
    documents: list[ExtractedDocumentFields],
) -> list[FieldMismatch]:
    conflicts: list[FieldMismatch] = []
    title_values = {document.title_number for document in documents if document.title_number}
    if certificate.title_number:
        title_values.add(certificate.title_number)
    if len(title_values) > 1:
        conflicts.append(
            FieldMismatch(
                code="title_number_mismatch",
                label="Search certificate title number mismatch",
                severity="high",
                values=sorted(title_values),
                explanation="The title number on the uploaded search certificate differs from another uploaded document.",
                evidence=certificate.evidence,
            )
        )
    parcel_values = {document.parcel_number for document in documents if document.parcel_number}
    if certificate.parcel_number:
        parcel_values.add(certificate.parcel_number)
    if len(parcel_values) > 1:
        conflicts.append(
            FieldMismatch(
                code="parcel_number_mismatch",
                label="Search certificate parcel number mismatch",
                severity="high",
                values=sorted(parcel_values),
                explanation="The parcel number on the uploaded search certificate differs from another uploaded document.",
                evidence=certificate.evidence,
            )
        )
    return conflicts


def _recommended_actions(factors: list[AgentRiskFactor]) -> list[str]:
    if not factors:
        return [
            "Proceed only after routine advocate, surveyor, and official registry checks are completed.",
            "Keep the report with the transaction file for audit and decision records.",
        ]
    actions = []
    for factor in factors[:6]:
        if factor.recommendation not in actions:
            actions.append(factor.recommendation)
    return actions


def _json_safe(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _case_like(profile: CaseProfile) -> Any:
    class CaseLike:
        id = profile.case_id
        title = profile.title
        buyer_name = profile.buyer_name
        seller_name = profile.seller_name
        parcel_number_claimed = profile.parcel_number_claimed
        location_county = profile.county
        preferred_language = profile.preferred_language

    return CaseLike()


def _bool_field(value: str) -> bool | None:
    if not value:
        return None
    return value.strip().lower() in {"true", "yes", "present", "signed"}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().upper()


def _mean(values: list[float]) -> float:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 2) if clean else 0.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.domain.enums import VerificationStatus
from app.models import Document, GazetteSearch, GazetteSearchResult, LandCase, Report, RiskAnalysisResult, VerificationAttempt


@dataclass(frozen=True)
class EvidenceSnippet:
    source_type: str
    title: str
    excerpt: str
    confidence: float | None = None
    document_id: str | None = None
    metadata: dict[str, Any] | None = None


def answer_case_question(
    *,
    case: LandCase,
    documents: list[Document],
    risk_analysis: RiskAnalysisResult | None,
    report: Report | None,
    gazette_searches: list[GazetteSearch],
    gazette_results: list[GazetteSearchResult],
    verification_attempts: list[VerificationAttempt],
    question: str,
) -> dict[str, Any]:
    snippets = _collect_snippets(
        case=case,
        documents=documents,
        risk_analysis=risk_analysis,
        report=report,
        gazette_searches=gazette_searches,
        gazette_results=gazette_results,
        verification_attempts=verification_attempts,
    )
    tokens = _tokens(question)
    ranked = _rank(snippets, tokens)
    official_status = _official_registry_status(verification_attempts)
    ownership_question = bool(tokens & {"owner", "ownership", "seller", "registered", "registry", "official"})

    if not ranked:
        return {
            "answer": (
                "I do not have enough uploaded-document, extracted-field, Gazette, or risk-analysis evidence in this case to answer that. "
                "Upload the relevant document or run analysis, then ask again."
            ),
            "citations": [],
            "limitations": [
                "The agent is restricted to the current case evidence.",
                "No official ownership verification is claimed unless an official registry result is recorded.",
            ],
            "verification_status": official_status,
        }

    top = ranked[:5]
    answer_parts: list[str] = []
    if ownership_question and official_status != VerificationStatus.VERIFIED.value:
        answer_parts.append(
            "The case does not contain recorded official registry ownership verification, "
            "so I can only summarize uploaded and extracted evidence."
        )
    answer_parts.extend(_sentence_from_snippet(snippet) for snippet in top[:3])
    return {
        "answer": " ".join(answer_parts),
        "citations": [
            {
                "source_type": snippet.source_type,
                "title": snippet.title,
                "excerpt": snippet.excerpt,
                "confidence": snippet.confidence,
                "document_id": snippet.document_id,
                "metadata": snippet.metadata or {},
            }
            for snippet in top
        ],
        "limitations": [
            "Answers are limited to uploaded documents, extracted fields, Gazette results, "
            "verification attempts, and risk analysis for this case.",
            "This is not legal advice or official registry proof.",
        ],
        "verification_status": official_status,
    }


def _collect_snippets(
    *,
    case: LandCase,
    documents: list[Document],
    risk_analysis: RiskAnalysisResult | None,
    report: Report | None,
    gazette_searches: list[GazetteSearch],
    gazette_results: list[GazetteSearchResult],
    verification_attempts: list[VerificationAttempt],
) -> list[EvidenceSnippet]:
    snippets = [
        EvidenceSnippet(
            source_type="case_input",
            title="Case details",
            excerpt=(
                f"Buyer: {case.buyer_name or 'not recorded'}; seller: {case.seller_name or 'not recorded'}; "
                f"parcel: {case.parcel_number_claimed or 'not recorded'}; title: {case.title_number or 'not recorded'}; "
                f"county: {case.location_county or 'not recorded'}; location: {case.location or 'not recorded'}."
            ),
            confidence=1.0,
        )
    ]
    for document in documents:
        quality = document.image_quality_score
        snippets.append(
            EvidenceSnippet(
                source_type="document",
                title=f"{document.category.value.replace('_', ' ')}: {document.filename}",
                excerpt=(
                    f"Uploaded document status is {document.status.value}; extraction status is {document.extraction_status}; "
                    f"quality score is {quality if quality is not None else 'not recorded'}."
                ),
                confidence=quality,
                document_id=document.id,
            )
        )
        for field in document.extracted_fields or []:
            snippets.append(
                EvidenceSnippet(
                    source_type="extracted_field",
                    title=f"{field.field_name.replace('_', ' ')} from {document.filename}",
                    excerpt=f"{field.field_name}: {field.value}. Source text: {field.text_snippet or field.value}",
                    confidence=field.confidence,
                    document_id=document.id,
                    metadata={"field_name": field.field_name, "document_category": document.category.value},
                )
            )
        for correction in document.field_corrections or []:
            snippets.append(
                EvidenceSnippet(
                    source_type="user_correction",
                    title=f"User correction for {correction.field_name}",
                    excerpt=(
                        f"{correction.field_name} was corrected from {correction.ai_value or 'not recorded'} "
                        f"to {correction.corrected_value}. Reason: {correction.reason or 'not recorded'}."
                    ),
                    confidence=1.0,
                    document_id=document.id,
                    metadata={"field_name": correction.field_name, "document_category": document.category.value},
                )
            )
    if risk_analysis is not None:
        payload = risk_analysis.result_json or {}
        snippets.append(
            EvidenceSnippet(
                source_type="risk_analysis",
                title="Latest risk analysis",
                excerpt=(
                    f"Risk score {risk_analysis.score}/100, level {risk_analysis.band.value}. "
                    f"Summary: {risk_analysis.summary}"
                ),
                confidence=1.0,
            )
        )
        for factor in payload.get("risk_factors", []) or []:
            if isinstance(factor, dict):
                snippets.append(
                    EvidenceSnippet(
                        source_type="risk_factor",
                        title=str(factor.get("label") or factor.get("code") or "Risk factor"),
                        excerpt=(
                            f"{factor.get('label') or factor.get('code')}: {factor.get('explanation') or ''} "
                            f"Recommendation: {factor.get('recommendation') or 'not recorded'}."
                        ),
                        confidence=_factor_confidence(factor),
                        metadata={"code": factor.get("code"), "severity": factor.get("severity")},
                    )
                )
    if report is not None:
        content = report.content or {}
        for warning in content.get("before_deposit_warnings", []) or []:
            if isinstance(warning, dict):
                snippets.append(
                    EvidenceSnippet(
                        source_type="before_deposit_warning",
                        title=str(warning.get("label") or warning.get("code") or "Before deposit warning"),
                        excerpt=f"{warning.get('explanation', '')} Recommended action: {warning.get('recommended_action', '')}",
                        confidence=1.0,
                        metadata={"code": warning.get("code"), "severity": warning.get("severity")},
                    )
                )
        for step in content.get("recommended_next_steps", []) or []:
            snippets.append(
                EvidenceSnippet(
                    source_type="next_step",
                    title="Recommended next step",
                    excerpt=str(step),
                    confidence=1.0,
                )
            )
    for search in gazette_searches:
        snippets.append(
            EvidenceSnippet(
                source_type="gazette_search",
                title="Gazette search status",
                excerpt=(
                    f"Gazette search status {search.status}; query terms: {', '.join(search.query_terms or [])}; "
                    f"message: {search.error_message or 'not recorded'}."
                ),
                confidence=1.0,
                metadata={"search_id": search.id},
            )
        )
    for result in gazette_results:
        snippets.append(
            EvidenceSnippet(
                source_type="gazette_result",
                title=result.notice_title,
                excerpt=f"{result.source_name}: {result.snippet}",
                confidence=result.confidence_score,
                metadata={"source_url": result.source_url, "publication_date": result.publication_date},
            )
        )
    for attempt in verification_attempts:
        snippets.append(
            EvidenceSnippet(
                source_type="verification_attempt",
                title=attempt.adapter_name,
                excerpt=f"Verification status {attempt.status.value}. {attempt.message}",
                confidence=1.0 if attempt.status == VerificationStatus.VERIFIED else None,
                metadata={"status": attempt.status.value, "query": attempt.query},
            )
        )
    return snippets


def _rank(snippets: list[EvidenceSnippet], tokens: set[str]) -> list[EvidenceSnippet]:
    if not tokens:
        return snippets[:5]
    scored: list[tuple[int, EvidenceSnippet]] = []
    for snippet in snippets:
        haystack = " ".join([snippet.source_type, snippet.title, snippet.excerpt]).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, snippet))
    return [snippet for _, snippet in sorted(scored, key=lambda item: item[0], reverse=True)]


def _sentence_from_snippet(snippet: EvidenceSnippet) -> str:
    confidence = f" Confidence {round(snippet.confidence * 100)}%." if snippet.confidence is not None else ""
    return f"{snippet.title}: {snippet.excerpt}{confidence}"


def _official_registry_status(attempts: list[VerificationAttempt]) -> str:
    if any(attempt.status == VerificationStatus.VERIFIED for attempt in attempts):
        return VerificationStatus.VERIFIED.value
    if any(attempt.status == VerificationStatus.CONFLICT_FOUND for attempt in attempts):
        return VerificationStatus.CONFLICT_FOUND.value
    if any(attempt.status == VerificationStatus.MANUAL_REVIEW_REQUIRED for attempt in attempts):
        return VerificationStatus.MANUAL_REVIEW_REQUIRED.value
    return VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE.value


def _factor_confidence(factor: dict[str, Any]) -> float | None:
    refs = factor.get("evidence_refs", []) or []
    evidence = factor.get("evidence")
    if isinstance(evidence, dict):
        refs = [*refs, *(evidence.get("evidence_refs", []) or []), *(evidence.get("evidence", []) or [])]
    confidences: list[float] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        try:
            confidences.append(float(ref.get("confidence")))
        except (TypeError, ValueError):
            continue
    return round(sum(confidences) / len(confidences), 2) if confidences else None


def _tokens(question: str) -> set[str]:
    stop = {
        "about",
        "after",
        "again",
        "against",
        "does",
        "from",
        "have",
        "is",
        "show",
        "that",
        "the",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
    return {token for token in re.findall(r"[a-z0-9]+", question.lower()) if len(token) > 2 and token not in stop}

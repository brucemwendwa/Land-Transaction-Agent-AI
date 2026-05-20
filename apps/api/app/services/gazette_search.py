from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.adapters.gazette import (
    CONFLICT_KEYWORDS,
    CombinedGazetteSearchResult,
    GazetteSourceAdapter,
    search_gazette_sources,
)
from app.domain.enums import VerificationStatus
from app.models import Document, GazetteSearch, GazetteSearchResult, LandCase, VerificationAttempt

SEARCH_FIELD_NAMES = {
    "parcel_number",
    "title_number",
    "owner_name",
    "seller_name",
    "county",
    "registry",
    "location",
}


async def run_gazette_search_for_case(
    *,
    db: Session,
    case: LandCase,
    sources: list[GazetteSourceAdapter] | None = None,
) -> CombinedGazetteSearchResult:
    documents = (
        db.query(Document)
        .options(selectinload(Document.extracted_fields), selectinload(Document.field_corrections))
        .filter(Document.case_id == case.id)
        .all()
    )
    query_terms = collect_gazette_query_terms(case=case, documents=documents)
    result = await search_gazette_sources(query_terms=query_terms, sources=sources)
    search = GazetteSearch(
        case_id=case.id,
        query_terms=result.query_terms,
        county=case.location_county,
        parcel_number=case.parcel_number_claimed,
        title_number=case.title_number,
        status=result.status,
        result_count=len(result.notices),
        error_message=result.message if result.status == "search_failed" else "",
        searched_at=_parse_checked_at(result.checked_at),
        metadata_json={"source_results": [asdict(source_result) for source_result in result.source_results]},
    )
    db.add(search)
    db.flush()
    for notice in result.notices:
        checked_at = _parse_checked_at(notice.checked_at)
        db.add(
            GazetteSearchResult(
                gazette_search_id=search.id,
                case_id=case.id,
                source_name=notice.source_name,
                notice_title=notice.notice_title,
                publication_date=notice.publication_date,
                matched_keywords=notice.matched_keywords,
                snippet=notice.snippet,
                source_url=notice.source_url,
                confidence_score=notice.confidence_score,
                checked_at=checked_at,
                metadata_json={"search_status": result.status, "query_terms": result.query_terms},
            )
        )
    db.add(
        VerificationAttempt(
            case_id=case.id,
            adapter_name="gazette_multi_source",
            status=_verification_status(result),
            query={"terms": result.query_terms},
            evidence={
                "status": result.status,
                "notices": [asdict(notice) for notice in result.notices],
                "source_results": [asdict(source_result) for source_result in result.source_results],
            },
            message=result.message,
        )
    )
    return result


def collect_gazette_query_terms(*, case: LandCase, documents: list[Document]) -> list[str]:
    terms = [
        case.parcel_number_claimed,
        case.seller_name,
        case.location_county,
        case.title,
    ]
    for document in documents:
        for field in document.extracted_fields or []:
            if field.field_name in SEARCH_FIELD_NAMES:
                terms.append(field.value)
        for correction in document.field_corrections or []:
            if correction.field_name in SEARCH_FIELD_NAMES:
                terms.append(correction.corrected_value)
    return _clean_terms(terms)


def serialize_gazette_search(result: CombinedGazetteSearchResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "query_terms": result.query_terms,
        "results": [asdict(notice) for notice in result.notices],
        "source_results": [asdict(source_result) for source_result in result.source_results],
        "message": result.message,
        "checked_at": result.checked_at,
        "disclaimer": (
            "Gazette search is one risk signal only. It does not replace an official land search, "
            "licensed advocate, licensed surveyor, or Ministry of Lands/National Land Commission due diligence."
        ),
    }


def _verification_status(result: CombinedGazetteSearchResult) -> VerificationStatus:
    if result.status == "checked_match_found":
        has_conflict_language = any(
            any(keyword in notice.snippet.lower() for keyword in CONFLICT_KEYWORDS)
            for notice in result.notices
        )
        return (
            VerificationStatus.CONFLICT_FOUND
            if has_conflict_language
            else VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE
        )
    if result.status == "search_failed":
        return VerificationStatus.ADAPTER_UNAVAILABLE
    if result.status == "manual_review_required":
        return VerificationStatus.MANUAL_REVIEW_REQUIRED
    if result.status == "not_configured":
        return VerificationStatus.NOT_CHECKED
    return VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE


def _parse_checked_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def _clean_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for term in terms:
        value = " ".join((term or "").split()).strip()
        if len(value) < 2:
            continue
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        clean.append(value)
    return clean

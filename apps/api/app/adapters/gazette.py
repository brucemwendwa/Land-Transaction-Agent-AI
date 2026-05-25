from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import urlencode, urljoin

import httpx

from app.adapters.verification import VerificationResult
from app.core.config import settings
from app.domain.enums import VerificationStatus

GazetteSearchStatus = Literal[
    "checked_no_match",
    "checked_match_found",
    "search_failed",
    "not_configured",
    "manual_review_required",
]

CONFLICT_KEYWORDS = {
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
}

_SOURCE_CACHE_TTL_SECONDS = 900
_source_cache: dict[str, tuple[float, GazetteSourceSearchResult]] = {}


@dataclass(frozen=True)
class GazetteSearchQuery:
    terms: list[str]


@dataclass(frozen=True)
class GazetteNoticeResult:
    source_name: str
    notice_title: str
    publication_date: str
    matched_keywords: list[str]
    snippet: str
    source_url: str
    confidence_score: float
    checked_at: str


@dataclass(frozen=True)
class GazetteSourceSearchResult:
    source_name: str
    status: GazetteSearchStatus
    query_terms: list[str]
    notices: list[GazetteNoticeResult] = field(default_factory=list)
    error: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class GazetteSourceAdapter(Protocol):
    source_name: str

    @property
    def configured(self) -> bool: ...

    async def search(self, query: GazetteSearchQuery) -> GazetteSourceSearchResult: ...


class KenyaLawGazetteAdapter:
    source_name = "Kenya Law Gazette"

    @property
    def configured(self) -> bool:
        return bool(settings.kenya_gazette_url)

    async def search(self, query: GazetteSearchQuery) -> GazetteSourceSearchResult:
        if not self.configured:
            return GazetteSourceSearchResult(
                source_name=self.source_name,
                status="not_configured",
                query_terms=query.terms,
                error="Kenya Law Gazette URL is not configured.",
            )
        return await _search_html_source(
            source_name=self.source_name,
            base_url=str(settings.kenya_gazette_url),
            query=query,
        )


class StateDepartmentLandsGazetteAdapter:
    source_name = "State Department for Lands Gazette"

    @property
    def configured(self) -> bool:
        return bool(settings.state_department_lands_gazette_url)

    async def search(self, query: GazetteSearchQuery) -> GazetteSourceSearchResult:
        if not self.configured:
            return GazetteSourceSearchResult(
                source_name=self.source_name,
                status="not_configured",
                query_terms=query.terms,
                error="STATE_DEPARTMENT_LANDS_GAZETTE_URL is not configured.",
            )
        return await _search_html_source(
            source_name=self.source_name,
            base_url=settings.state_department_lands_gazette_url,
            query=query,
        )


class KenyaGazetteAdapter:
    """Compatibility facade used by the ADK GazetteSearchAgent."""

    name = "gazette_multi_source"

    def __init__(self, sources: list[GazetteSourceAdapter] | None = None) -> None:
        self.sources = sources or [KenyaLawGazetteAdapter(), StateDepartmentLandsGazetteAdapter()]

    async def search_terms(self, query_terms: list[str]) -> VerificationResult:
        result = await search_gazette_sources(query_terms=query_terms, sources=self.sources)
        if result.status == "checked_match_found":
            has_conflict = any(
                any(keyword in notice.snippet.lower() for keyword in CONFLICT_KEYWORDS)
                for notice in result.notices
            )
            return VerificationResult(
                adapter_name=self.name,
                status=VerificationStatus.CONFLICT_FOUND
                if has_conflict
                else VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
                query={"terms": result.query_terms, "sources": [item.source_name for item in result.source_results]},
                evidence={"hits": [notice_as_legacy_hit(notice) for notice in result.notices]},
                message=(
                    "Potential Gazette notice conflict found."
                    if has_conflict
                    else "Gazette mentions found; review manually because this is not ownership verification."
                ),
            )
        if result.status == "search_failed":
            return VerificationResult(
                adapter_name=self.name,
                status=VerificationStatus.ADAPTER_UNAVAILABLE,
                query={"terms": result.query_terms},
                evidence={"source_results": [asdict(item) for item in result.source_results]},
                message=result.message,
            )
        if result.status == "manual_review_required":
            return VerificationResult(
                adapter_name=self.name,
                status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                query={"terms": result.query_terms},
                message=result.message,
            )
        if result.status == "not_configured":
            return VerificationResult(
                adapter_name=self.name,
                status=VerificationStatus.NOT_CHECKED,
                query={"terms": result.query_terms},
                evidence={"source_results": [asdict(item) for item in result.source_results]},
                message=result.message,
            )
        return VerificationResult(
            adapter_name=self.name,
            status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
            query={"terms": result.query_terms, "sources": [item.source_name for item in result.source_results]},
            evidence={"hits": []},
            message=result.message,
        )

    async def search(self, parcel_number: str) -> VerificationResult:
        return await self.search_terms([parcel_number])


@dataclass(frozen=True)
class CombinedGazetteSearchResult:
    status: GazetteSearchStatus
    query_terms: list[str]
    notices: list[GazetteNoticeResult]
    source_results: list[GazetteSourceSearchResult]
    message: str
    checked_at: str


async def search_gazette_sources(
    *,
    query_terms: list[str],
    sources: list[GazetteSourceAdapter] | None = None,
) -> CombinedGazetteSearchResult:
    clean_terms = _clean_terms(query_terms)
    checked_at = datetime.now(UTC).isoformat()
    if not clean_terms:
        return CombinedGazetteSearchResult(
            status="manual_review_required",
            query_terms=[],
            notices=[],
            source_results=[],
            message="Gazette search needs at least one parcel/title/LR number, owner, county, registry, or location keyword.",
            checked_at=checked_at,
        )
    source_adapters = sources or [KenyaLawGazetteAdapter(), StateDepartmentLandsGazetteAdapter()]
    source_results = [await source.search(GazetteSearchQuery(terms=clean_terms)) for source in source_adapters]
    notices = _dedupe_notices([notice for result in source_results for notice in result.notices])
    if notices:
        return CombinedGazetteSearchResult(
            status="checked_match_found",
            query_terms=clean_terms,
            notices=notices,
            source_results=source_results,
            message="Possible Gazette match found. Review the source notice before treating it as a risk signal.",
            checked_at=checked_at,
        )
    statuses = {result.status for result in source_results}
    if statuses == {"not_configured"}:
        status: GazetteSearchStatus = "not_configured"
        message = "No Gazette source adapter is configured."
    elif statuses and statuses <= {"search_failed", "not_configured"}:
        status = "search_failed"
        message = "Configured Gazette source search failed or was unavailable."
    else:
        status = "checked_no_match"
        message = "No matching Gazette notice was found in configured sources."
    return CombinedGazetteSearchResult(
        status=status,
        query_terms=clean_terms,
        notices=[],
        source_results=source_results,
        message=message,
        checked_at=checked_at,
    )


async def _search_html_source(
    *,
    source_name: str,
    base_url: str,
    query: GazetteSearchQuery,
) -> GazetteSourceSearchResult:
    checked_at = datetime.now(UTC).isoformat()
    cache_key = f"{source_name}:{base_url}:{'|'.join(query.terms)}"
    cached = _source_cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]
    notices: list[GazetteNoticeResult] = []
    attempted_terms: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for term in query.terms[:10]:
                attempted_terms.append(term)
                query_url = f"{base_url}?{urlencode({'q': term})}"
                response = await _get_with_retries(client, query_url)
                notices.extend(
                    _extract_hits(
                        html=response.text,
                        term=term,
                        source_name=source_name,
                        source_url=query_url,
                        checked_at=checked_at,
                    )
                )
    except httpx.HTTPError as exc:
        return GazetteSourceSearchResult(
            source_name=source_name,
            status="search_failed",
            query_terms=attempted_terms or query.terms,
            error=str(exc),
            checked_at=checked_at,
        )
    result = GazetteSourceSearchResult(
        source_name=source_name,
        status="checked_match_found" if notices else "checked_no_match",
        query_terms=attempted_terms,
        notices=_dedupe_notices(notices),
        checked_at=checked_at,
    )
    _source_cache[cache_key] = (time.time() + _SOURCE_CACHE_TTL_SECONDS, result)
    return result


async def _get_with_retries(client: httpx.AsyncClient, url: str, *, attempts: int = 3) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            await _sleep_backoff(attempt)
    raise last_error or httpx.HTTPError("Gazette request failed")


async def _sleep_backoff(attempt: int) -> None:
    import asyncio

    await asyncio.sleep(0.35 * (attempt + 1))


def _extract_hits(
    *,
    html: str,
    term: str,
    source_name: str,
    source_url: str,
    checked_at: str,
) -> list[GazetteNoticeResult]:
    normalized = re.sub(r"\s+", " ", html)
    hits: list[GazetteNoticeResult] = []
    for match in re.finditer(re.escape(term.strip()), normalized, re.I):
        start = max(0, match.start() - 220)
        end = min(len(normalized), match.end() + 260)
        raw_snippet = normalized[start:end]
        snippet = re.sub("<[^>]+>", " ", raw_snippet).strip()
        href_match = re.search(r'href=["\']([^"\']+)["\']', raw_snippet)
        title = _extract_title(raw_snippet) or "Gazette notice mention"
        publication_date = _extract_date(snippet)
        matched_keywords = sorted({term, *[word for word in CONFLICT_KEYWORDS if word in snippet.lower()]})
        confidence = 0.76 if any(word in snippet.lower() for word in CONFLICT_KEYWORDS) else 0.62
        hits.append(
            GazetteNoticeResult(
                source_name=source_name,
                notice_title=title,
                publication_date=publication_date,
                matched_keywords=matched_keywords,
                snippet=snippet[:800],
                source_url=urljoin(source_url, href_match.group(1)) if href_match else source_url,
                confidence_score=confidence,
                checked_at=checked_at,
            )
        )
    return hits


def _extract_title(raw_snippet: str) -> str:
    for pattern in [r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"<title[^>]*>(.*?)</title>", r'aria-label=["\']([^"\']+)["\']']:
        if match := re.search(pattern, raw_snippet, re.I):
            return re.sub("<[^>]+>", " ", match.group(1)).strip()
    return ""


def _extract_date(snippet: str) -> str:
    if match := re.search(r"\b([0-3]?\d\s+[A-Z][a-z]+\s+(?:19|20)\d{2})\b", snippet):
        return match.group(1)
    if match := re.search(r"\b((?:19|20)\d{2}[-/][01]?\d[-/][0-3]?\d)\b", snippet):
        return match.group(1)
    return ""


def _clean_terms(query_terms: list[str]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for term in query_terms:
        normalized = re.sub(r"\s+", " ", term or "").strip()
        if len(normalized) < 2:
            continue
        key = normalized.upper()
        if key in seen:
            continue
        seen.add(key)
        clean.append(normalized)
    return clean[:20]


def _dedupe_notices(notices: list[GazetteNoticeResult]) -> list[GazetteNoticeResult]:
    deduped: dict[tuple[str, str, str], GazetteNoticeResult] = {}
    for notice in notices:
        key = (notice.source_name, notice.source_url, notice.snippet[:120])
        existing = deduped.get(key)
        if existing is None or notice.confidence_score > existing.confidence_score:
            deduped[key] = notice
    return sorted(deduped.values(), key=lambda item: item.confidence_score, reverse=True)


def notice_as_legacy_hit(notice: GazetteNoticeResult) -> dict[str, str | float | list[str]]:
    return {
        "source": notice.source_name,
        "date": notice.publication_date,
        "title": notice.notice_title,
        "url": notice.source_url,
        "snippet": notice.snippet,
        "confidence": notice.confidence_score,
        "matched_keywords": notice.matched_keywords,
    }

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.adapters.gazette import (
    GazetteNoticeResult,
    GazetteSearchQuery,
    GazetteSourceSearchResult,
    search_gazette_sources,
)
from app.db.session import SessionLocal
from app.domain.enums import DocumentCategory, DocumentStatus, VerificationStatus
from app.models import Document, ExtractedField, GazetteSearch, GazetteSearchResult, LandCase, User, VerificationAttempt
from app.services.gazette_search import run_gazette_search_for_case


class FakeSource:
    def __init__(
        self,
        *,
        source_name: str,
        status: str,
        notices: list[GazetteNoticeResult] | None = None,
        error: str = "",
    ) -> None:
        self.source_name = source_name
        self.status = status
        self.notices = notices or []
        self.error = error

    @property
    def configured(self) -> bool:
        return self.status != "not_configured"

    async def search(self, query: GazetteSearchQuery) -> GazetteSourceSearchResult:
        return GazetteSourceSearchResult(
            source_name=self.source_name,
            status=self.status,  # type: ignore[arg-type]
            query_terms=query.terms,
            notices=self.notices,
            error=self.error,
        )


def notice(title: str, keyword: str = "LR 209/1234") -> GazetteNoticeResult:
    return GazetteNoticeResult(
        source_name="Fixture Gazette",
        notice_title=title,
        publication_date="2025-01-10",
        matched_keywords=[keyword],
        snippet=f"Notice mentions {keyword}",
        source_url=f"https://example.test/{title.replace(' ', '-')}",
        confidence_score=0.82,
        checked_at=datetime.now(UTC).isoformat(),
    )


def test_gazette_successful_search() -> None:
    result = asyncio.run(
        search_gazette_sources(
            query_terms=["LR 209/1234"],
            sources=[FakeSource(source_name="Fixture", status="checked_match_found", notices=[notice("Restriction notice")])],
        )
    )
    assert result.status == "checked_match_found"
    assert result.notices[0].notice_title == "Restriction notice"


def test_gazette_no_match() -> None:
    result = asyncio.run(
        search_gazette_sources(
            query_terms=["LR 209/1234"],
            sources=[FakeSource(source_name="Fixture", status="checked_no_match")],
        )
    )
    assert result.status == "checked_no_match"
    assert result.notices == []


def test_gazette_failed_search() -> None:
    result = asyncio.run(
        search_gazette_sources(
            query_terms=["LR 209/1234"],
            sources=[FakeSource(source_name="Fixture", status="search_failed", error="timeout")],
        )
    )
    assert result.status == "search_failed"
    assert result.source_results[0].error == "timeout"


def test_gazette_multiple_possible_matches() -> None:
    result = asyncio.run(
        search_gazette_sources(
            query_terms=["LR 209/1234", "John Mwangi"],
            sources=[
                FakeSource(
                    source_name="Fixture",
                    status="checked_match_found",
                    notices=[notice("Restriction notice"), notice("Compulsory acquisition notice")],
                )
            ],
        )
    )
    assert result.status == "checked_match_found"
    assert len(result.notices) == 2


def test_gazette_search_persists_normalized_results_and_attempt() -> None:
    db = SessionLocal()
    try:
        user = User(clerk_user_id="gazette-user", email="gazette@example.test", full_name="Gazette User")
        db.add(user)
        db.flush()
        land_case = LandCase(
            owner_user_id=user.id,
            title="Gazette persistence case",
            seller_name="John Mwangi",
            parcel_number_claimed="LR 209/1234",
        )
        db.add(land_case)
        db.flush()
        document = Document(
            case_id=land_case.id,
            uploaded_by_user_id=user.id,
            category=DocumentCategory.TITLE_DEED,
            filename="title.pdf",
            content_type="application/pdf",
            file_size=100,
            storage_uri="local://clean/title.pdf",
            status=DocumentStatus.EXTRACTED,
        )
        db.add(document)
        db.flush()
        db.add(
            ExtractedField(
                document_id=document.id,
                field_name="parcel_number",
                value="LR 209/1234",
                normalized_value="LR 209/1234",
                confidence=0.9,
                source="fixture",
            )
        )
        db.commit()

        result = asyncio.run(
            run_gazette_search_for_case(
                db=db,
                case=land_case,
                sources=[FakeSource(source_name="Fixture", status="checked_match_found", notices=[notice("Restriction notice")])],
            )
        )
        db.commit()
        assert result.status == "checked_match_found"
        stored = db.query(GazetteSearchResult).filter(GazetteSearchResult.case_id == land_case.id).one()
        assert stored.source_name == "Fixture Gazette"
        assert stored.matched_keywords == ["LR 209/1234"]
        attempt = db.query(VerificationAttempt).filter(VerificationAttempt.case_id == land_case.id).one()
        assert attempt.adapter_name == "gazette_multi_source"
        assert attempt.evidence["status"] == "checked_match_found"
    finally:
        db.close()


def test_gazette_search_failure_is_persisted_as_adapter_unavailable() -> None:
    db = SessionLocal()
    try:
        user = User(clerk_user_id="gazette-user", email="gazette@example.test", full_name="Gazette User")
        db.add(user)
        db.flush()
        land_case = LandCase(
            owner_user_id=user.id,
            title="Gazette failure case",
            seller_name="John Mwangi",
            parcel_number_claimed="LR 209/1234",
        )
        db.add(land_case)
        db.commit()

        result = asyncio.run(
            run_gazette_search_for_case(
                db=db,
                case=land_case,
                sources=[FakeSource(source_name="Fixture", status="search_failed", error="timeout")],
            )
        )
        db.commit()

        assert result.status == "search_failed"
        stored = db.query(GazetteSearch).filter(GazetteSearch.case_id == land_case.id).one()
        assert stored.error_message == "Configured Gazette source search failed or was unavailable."
        attempt = db.query(VerificationAttempt).filter(VerificationAttempt.case_id == land_case.id).one()
        assert attempt.status == VerificationStatus.ADAPTER_UNAVAILABLE
        assert attempt.evidence["source_results"][0]["error"] == "timeout"
    finally:
        db.close()

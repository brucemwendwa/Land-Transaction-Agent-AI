from __future__ import annotations

from app.domain.enums import DocumentCategory, VerificationStatus
from app.services.extraction import extract_document_fields, extraction_provider_status, normalize, normalize_date


def test_deterministic_extraction_finds_land_document_facts_with_evidence() -> None:
    content = (
        b"Title Number: TITLE 42\n"
        b"Parcel No: LR 209/1234\n"
        b"Owner: John Mwangi\n"
        b"Registry: Kajiado\n"
        b"County: Kajiado\n"
        b"Signature present\n"
        b"Seal present\n"
        b"Date: 19/05/2026"
    )

    fields, quality, status, raw_text = extract_document_fields(
        content=content,
        content_type="text/plain",
        category=DocumentCategory.TITLE_DEED,
    )
    by_name = {field.field_name: field for field in fields}

    assert status == VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE
    assert quality is not None and quality > 0.2
    assert "Parcel No: LR 209/1234" in raw_text
    assert by_name["parcel_number"].value == "LR 209/1234"
    assert by_name["owner_name"].value == "John Mwangi"
    assert by_name["title_number"].value == "TITLE 42"
    assert by_name["document_date"].normalized_value == "2026-05-19"
    assert by_name["parcel_number"].text_snippet
    assert extraction_provider_status(content_type="text/plain", fields=fields, raw_text=raw_text) == "completed"


def test_image_extraction_without_providers_is_transparent() -> None:
    fields, quality, status, raw_text = extract_document_fields(
        content=b"not really an image",
        content_type="image/jpeg",
        category=DocumentCategory.TITLE_DEED,
    )

    assert fields == []
    assert quality == 0.35 or quality is None
    assert status == VerificationStatus.MANUAL_REVIEW_REQUIRED
    assert extraction_provider_status(content_type="image/jpeg", fields=fields, raw_text=raw_text) == "provider_not_configured"


def test_normalizers_make_dates_and_names_comparable() -> None:
    assert normalize("  lr   209/1234 ") == "LR 209/1234"
    assert normalize_date("19 May 2026") == "2026-05-19"
    assert normalize_date("2026/05/19") == "2026-05-19"

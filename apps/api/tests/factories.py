from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.enums import DocumentCategory, DocumentStatus
from app.models import Document, ExtractedField, FieldCorrection, LandCase, User


def make_user(**overrides: Any) -> User:
    values = {
        "clerk_user_id": "dev-user",
        "email": "buyer@example.test",
        "full_name": "Local Buyer",
    }
    values.update(overrides)
    return User(**values)


def make_case(**overrides: Any) -> LandCase:
    values = {
        "id": "case-1",
        "owner_user_id": "user-1",
        "title": "Kajiado parcel",
        "buyer_name": "Jane Wanjiku",
        "seller_name": "John Mwangi",
        "parcel_number_claimed": "LR 209/1234",
        "location_county": "Kajiado",
        "payment_before_verification": False,
    }
    values.update(overrides)
    return LandCase(**values)


def make_field(
    document_id: str,
    field_name: str,
    value: str,
    *,
    confidence: float = 0.9,
    source: str = "fixture",
) -> ExtractedField:
    return ExtractedField(
        id=f"{document_id}-{field_name}-{abs(hash((field_name, value))) % 100000}",
        document_id=document_id,
        field_name=field_name,
        value=value,
        normalized_value=value.strip().upper(),
        confidence=confidence,
        source=source,
        page_number=1,
        text_snippet=f"{field_name}: {value}",
    )


def make_document(
    category: DocumentCategory,
    document_id: str,
    *,
    parcel: str = "LR 209/1234",
    title_number: str = "TITLE 1",
    owner: str = "John Mwangi",
    seller: str = "John Mwangi",
    document_date: date | None = None,
    quality: float | None = 0.9,
    fields: list[tuple[str, str]] | None = None,
    extraction_warnings: list[dict[str, Any]] | None = None,
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
        extraction_warnings=extraction_warnings or [],
    )
    base_fields: list[tuple[str, str]] = []
    if category in {
        DocumentCategory.TITLE_DEED,
        DocumentCategory.SALE_AGREEMENT,
        DocumentCategory.LAND_SEARCH_CERTIFICATE,
        DocumentCategory.MUTATION_FORM,
        DocumentCategory.SURVEY_MAP,
    }:
        base_fields.append(("parcel_number", parcel))
    if category == DocumentCategory.TITLE_DEED:
        base_fields.extend([("owner_name", owner), ("title_number", title_number)])
    if category == DocumentCategory.LAND_SEARCH_CERTIFICATE:
        base_fields.extend([("owner_name", owner), ("title_number", title_number)])
    if category == DocumentCategory.SALE_AGREEMENT:
        base_fields.extend(
            [
                ("seller_name", seller),
                ("signatures_present", "true"),
                ("seals_present", "true"),
            ]
        )
    if category == DocumentCategory.KRA_PIN_CERTIFICATE:
        base_fields.append(("kra_pin", "A123456789B"))
    if category == DocumentCategory.NATIONAL_ID_OR_PASSPORT:
        base_fields.append(("id_number", "12345678"))
    if document_date:
        base_fields.append(("document_date", document_date.isoformat()))
    base_fields.extend(fields or [])
    document.extracted_fields = [
        make_field(document_id, field_name, value)
        for field_name, value in base_fields
        if value
    ]
    document.field_corrections = []
    return document


def make_core_documents(*, search_date: date | None = None) -> list[Document]:
    return [
        make_document(DocumentCategory.TITLE_DEED, "title"),
        make_document(DocumentCategory.SALE_AGREEMENT, "sale"),
        make_document(DocumentCategory.NATIONAL_ID_OR_PASSPORT, "id"),
        make_document(DocumentCategory.KRA_PIN_CERTIFICATE, "kra"),
        make_document(DocumentCategory.LAND_SEARCH_CERTIFICATE, "search", document_date=search_date or date.today()),
        make_document(DocumentCategory.CONSENT_TO_TRANSFER, "consent"),
        make_document(DocumentCategory.RATES_CLEARANCE_CERTIFICATE, "rates"),
        make_document(DocumentCategory.LAND_RENT_CLEARANCE_CERTIFICATE, "rent"),
    ]


def make_correction(
    *,
    document_id: str,
    field: ExtractedField,
    corrected_value: str,
    reason: str = "Confirmed during buyer review",
) -> FieldCorrection:
    return FieldCorrection(
        id=f"correction-{field.id}",
        document_id=document_id,
        extracted_field_id=field.id,
        corrected_by_user_id="user-1",
        field_name=field.field_name,
        ai_value=field.value,
        corrected_value=corrected_value,
        normalized_value=corrected_value.strip().upper(),
        reason=reason,
        metadata_json={"preserves_ai_extraction": True, "source": "user_review"},
    )

from __future__ import annotations

import io
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.core.config import settings
from app.domain.enums import DocumentCategory, VerificationStatus


@dataclass(frozen=True)
class FieldExtraction:
    field_name: str
    value: str
    normalized_value: str
    confidence: float
    source: str
    page_number: int | None = None
    bounding_box: dict[str, Any] | None = None
    text_snippet: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExtractionProviderResult:
    provider_name: str
    status: str
    fields: list[FieldExtraction]
    text: str = ""
    detail: str = ""


class ExtractionProvider(Protocol):
    provider_name: str

    @property
    def configured(self) -> bool: ...

    def extract(self, *, content: bytes, content_type: str, category: DocumentCategory) -> ExtractionProviderResult: ...


class LocalTextProvider:
    provider_name = "local_text"

    @property
    def configured(self) -> bool:
        return True

    def extract(self, *, content: bytes, content_type: str, category: DocumentCategory) -> ExtractionProviderResult:
        pages = extract_text_pages_from_bytes(content, content_type)
        text = "\n".join(page for page in pages if page).strip()
        if not text:
            return ExtractionProviderResult(
                provider_name=self.provider_name,
                status="no_text_found",
                fields=[],
                text="",
                detail="No native text was found in the file.",
            )
        return ExtractionProviderResult(
            provider_name=self.provider_name,
            status="completed",
            fields=list(_deterministic_fields(pages, category, self.provider_name)),
            text=text,
            detail="Extracted fields from native text.",
        )


class DocumentAIProvider:
    provider_name = "document_ai"

    @property
    def configured(self) -> bool:
        return settings.document_ai_enabled

    def extract(self, *, content: bytes, content_type: str, category: DocumentCategory) -> ExtractionProviderResult:
        if not self.configured:
            return ExtractionProviderResult(
                provider_name=self.provider_name,
                status="provider_not_configured",
                fields=[],
                detail="Google Document AI is not configured.",
            )
        text = run_document_ai_ocr(content, content_type)
        pages = [text] if text else []
        return ExtractionProviderResult(
            provider_name=self.provider_name,
            status="completed" if text else "no_text_found",
            fields=list(_deterministic_fields(pages, category, self.provider_name)),
            text=text,
            detail="Extracted fields with Google Document AI.",
        )


class GeminiVisionProvider:
    provider_name = "gemini_vision"

    @property
    def configured(self) -> bool:
        return settings.gemini_vision_enabled

    def extract(self, *, content: bytes, content_type: str, category: DocumentCategory) -> ExtractionProviderResult:
        if not self.configured:
            return ExtractionProviderResult(
                provider_name=self.provider_name,
                status="provider_not_configured",
                fields=[],
                detail="Gemini Vision is not configured.",
            )
        fields = run_gemini_vision_extraction(content=content, content_type=content_type, category=category)
        return ExtractionProviderResult(
            provider_name=self.provider_name,
            status="completed" if fields else "no_fields_found",
            fields=fields,
            detail="Extracted visual fields with Gemini Vision.",
        )


class GeminiVisionField(BaseModel):
    field_name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    page_number: int | None = None
    bounding_box: dict[str, Any] | None = None
    text_snippet: str = ""


class GeminiVisionExtraction(BaseModel):
    document_type: str = ""
    document_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fields: list[GeminiVisionField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


DATE_PATTERNS = [
    r"\b([0-3]?\d[/-][01]?\d[/-](?:19|20)\d{2})\b",
    r"\b((?:19|20)\d{2}[/-][01]?\d[/-][0-3]?\d)\b",
    r"\b([0-3]?\d\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2})\b",
]
ID_PATTERN = re.compile(r"\b(?:ID|Passport|National\s+ID|ID\s+No\.?)[:\s-]*([A-Z0-9]{6,12})\b", re.I)
KRA_PATTERN = re.compile(r"\b([AP]\d{9}[A-Z])\b", re.I)
PARCEL_PATTERNS = [
    re.compile(r"\b(?:LR|L\.R\.|Parcel|Plot)\s*(?:No\.?|Number|#)?\s*[:/-]?\s*([A-Z0-9/.\-\s]{4,80})", re.I),
    re.compile(r"\b([A-Z][A-Z\s-]{2,40}/(?:BLOCK\s*)?\d+[A-Z]?/\d+[A-Z]?)\b", re.I),
]
OWNER_PATTERN = re.compile(r"\b(?:Owner|Proprietor|Seller|Transferor)[:\s-]+([A-Z][A-Z .,'-]{3,120})", re.I)
BUYER_PATTERN = re.compile(r"\b(?:Buyer|Purchaser|Transferee)[:\s-]+([A-Z][A-Z .,'-]{3,120})", re.I)
REGISTRY_PATTERN = re.compile(r"\b(?:Registry|Land Registry)[:\s-]+([A-Z][A-Z .,'-]{2,80})", re.I)
COUNTY_PATTERN = re.compile(r"\bCounty[:\s-]+([A-Z][A-Z .,'-]{2,80})", re.I)
TITLE_PATTERN = re.compile(r"\b(?:Title\s*(?:No\.?|Number)|Certificate\s*of\s*Title\s*No\.?)[:\s-]+([A-Z0-9/.\-\s]{3,80})", re.I)
BLOCK_PATTERN = re.compile(r"\bBlock\s*(?:No\.?|Number)?[:\s-]*([A-Z0-9/-]{1,40})", re.I)
PLOT_PATTERN = re.compile(r"\bPlot\s*(?:No\.?|Number)?[:\s-]*([A-Z0-9/-]{1,40})", re.I)
LAND_SIZE_PATTERN = re.compile(r"\b(?:Area|Land\s*Size|Size)[:\s-]+([0-9,.]+\s*(?:ha|hectares|acres|sqm|m2|square\s*metres))", re.I)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).upper()


def extract_text_pages_from_bytes(content: bytes, content_type: str) -> list[str]:
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        return [(page.extract_text() or "").strip() for page in reader.pages]
    if content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        return [content.decode("utf-8", errors="ignore").strip()]
    return []


def extract_text_from_bytes(content: bytes, content_type: str) -> str:
    return "\n".join(page for page in extract_text_pages_from_bytes(content, content_type) if page).strip()


def run_document_ai_ocr(content: bytes, content_type: str) -> str:
    if not settings.document_ai_enabled:
        return ""
    from google.cloud import documentai

    client = documentai.DocumentProcessorServiceClient()
    name = client.processor_path(
        settings.gcp_project_id, settings.gcp_location, settings.document_ai_processor_id
    )
    raw_document = documentai.RawDocument(content=content, mime_type=content_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    return result.document.text or ""


def extract_document_fields(
    *,
    content: bytes,
    content_type: str,
    category: DocumentCategory,
) -> tuple[list[FieldExtraction], float | None, VerificationStatus, str]:
    results = [
        provider.extract(content=content, content_type=content_type, category=category)
        for provider in [LocalTextProvider(), DocumentAIProvider(), GeminiVisionProvider()]
    ]
    text = next((result.text for result in results if result.text), "")
    fields = [
        FieldExtraction(
            **{
                **field.__dict__,
                "metadata": {
                    **(field.metadata or {}),
                    "provider_statuses": {result.provider_name: result.status for result in results},
                },
            }
        )
        for result in results
        for field in result.fields
    ]
    quality = estimate_quality(text, content_type)
    status = (
        VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE
        if fields
        else VerificationStatus.MANUAL_REVIEW_REQUIRED
    )
    return fields, quality, status, text


def extraction_provider_status(*, content_type: str, fields: list[FieldExtraction], raw_text: str) -> str:
    if fields:
        return "completed"
    if raw_text:
        return "no_structured_fields"
    if content_type == "application/pdf" or content_type.startswith("text/"):
        return "no_text_found"
    if not settings.document_ai_enabled and not settings.gemini_vision_enabled:
        return "provider_not_configured"
    return "manual_review_required"


def _deterministic_fields(
    pages: list[str], category: DocumentCategory, source: str
) -> Iterable[FieldExtraction]:
    text = "\n".join(page for page in pages if page).strip()
    if not text.strip():
        return
    for page_number, page_text in enumerate(pages or [text], start=1):
        for pattern in PARCEL_PATTERNS:
            for match in pattern.finditer(page_text):
                value = _clean_parcel(match.group(1))
                if value:
                    yield _field("parcel_number", value, 0.78, source, page_number, page_text, match)
        for match in OWNER_PATTERN.finditer(page_text):
            value = match.group(1).strip(" .,:;\n")
            yield _field("owner_name", value, 0.72, source, page_number, page_text, match)
            if category in {DocumentCategory.SALE_AGREEMENT, DocumentCategory.TITLE_DEED}:
                yield _field("seller_name", value, 0.64, source, page_number, page_text, match)
        for match in BUYER_PATTERN.finditer(page_text):
            value = match.group(1).strip(" .,:;\n")
            yield _field("buyer_name", value, 0.72, source, page_number, page_text, match)
        for match in ID_PATTERN.finditer(page_text):
            value = match.group(1).strip()
            yield _field("id_number", value, 0.74, source, page_number, page_text, match)
        for match in KRA_PATTERN.finditer(page_text):
            value = match.group(1).strip()
            yield _field("kra_pin", value, 0.82, source, page_number, page_text, match)
        for date_value, date_match in _find_dates(page_text):
            yield _field("document_date", date_value, 0.68, source, page_number, page_text, date_match, normalize_date(date_value))
        for keyword in ["caution", "restriction", "charge", "encumbrance"]:
            keyword_match = re.search(re.escape(keyword), page_text, re.I)
            if keyword_match:
                yield _field("encumbrance_keyword", keyword, 0.66, source, page_number, page_text, keyword_match, keyword)
        for keyword in ["altered", "overwritten", "eraser", "missing seal", "inconsistent font"]:
            keyword_match = re.search(re.escape(keyword), page_text, re.I)
            if keyword_match:
                yield _field("visual_suspicion", keyword, 0.58, source, page_number, page_text, keyword_match, keyword)
        signature_match = re.search(r"\b(signature|signed)\b", page_text, re.I)
        if signature_match:
            yield _field("signatures_present", "true", 0.62, source, page_number, page_text, signature_match, "TRUE")
        seal_match = re.search(r"\b(seal|stamp)\b", page_text, re.I)
        if seal_match:
            yield _field("seals_present", "true", 0.62, source, page_number, page_text, seal_match, "TRUE")

    title_match = TITLE_PATTERN.search(text)
    if title_match:
        value = _clean_parcel(title_match.group(1))
        yield _field("title_number", value, 0.74, source, _page_for_match(pages, title_match.group(0)), text, title_match)
    block_match = BLOCK_PATTERN.search(text)
    if block_match:
        value = block_match.group(1).strip(" .,:;\n")
        yield _field("block", value, 0.68, source, _page_for_match(pages, block_match.group(0)), text, block_match)
    plot_match = PLOT_PATTERN.search(text)
    if plot_match:
        value = plot_match.group(1).strip(" .,:;\n")
        yield _field("plot_number", value, 0.68, source, _page_for_match(pages, plot_match.group(0)), text, plot_match)
    registry_match = REGISTRY_PATTERN.search(text)
    if registry_match:
        value = registry_match.group(1).strip(" .,:;\n")
        yield _field("registry", value, 0.65, source, _page_for_match(pages, registry_match.group(0)), text, registry_match)
    county_match = COUNTY_PATTERN.search(text)
    if county_match:
        value = county_match.group(1).strip(" .,:;\n")
        yield _field("county", value, 0.65, source, _page_for_match(pages, county_match.group(0)), text, county_match)
    land_size_match = LAND_SIZE_PATTERN.search(text)
    if land_size_match:
        value = land_size_match.group(1).strip(" .,:;\n")
        yield _field("land_size", value, 0.67, source, _page_for_match(pages, land_size_match.group(0)), text, land_size_match)


def run_gemini_vision_extraction(
    *, content: bytes, content_type: str, category: DocumentCategory
) -> list[FieldExtraction]:
    if not settings.gemini_vision_enabled:
        return []
    try:
        from google import genai
        from google.genai import types
    except Exception:
        return []
    try:
        client = genai.Client(
            vertexai=settings.google_genai_use_vertexai,
            project=settings.gcp_project_id or None,
            location=settings.vertex_ai_location,
            api_key=settings.google_api_key or None,
        )
        prompt = (
            "Extract Kenyan land transaction document fields as strict JSON. "
            "Return only evidence-backed fields. Do not infer missing values. "
            "Schema: {document_type, document_type_confidence, warnings, fields:["
            "{field_name,value,confidence,page_number,bounding_box,text_snippet}]}. "
            f"The user selected category is {category.value}."
        )
        contents: list[Any] = [
            types.Part.from_bytes(data=content, mime_type=content_type),
            prompt,
        ]
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
        )
        raw_text = getattr(response, "text", "") or ""
        payload = _json_from_model_text(raw_text)
        parsed = GeminiVisionExtraction.model_validate(payload)
    except Exception:
        return []
    return [
        FieldExtraction(
            field_name=field.field_name,
            value=field.value,
            normalized_value=normalize(field.value),
            confidence=field.confidence,
            source="gemini_vision",
            page_number=field.page_number,
            bounding_box=field.bounding_box,
            text_snippet=field.text_snippet[:500],
            metadata={
                "document_type": parsed.document_type,
                "document_type_confidence": parsed.document_type_confidence,
                "warnings": parsed.warnings,
            },
        )
        for field in parsed.fields
        if field.value.strip()
    ]


def _field(
    field_name: str,
    value: str,
    confidence: float,
    source: str,
    page_number: int | None,
    text: str,
    match: re.Match[str],
    normalized_value: str | None = None,
) -> FieldExtraction:
    return FieldExtraction(
        field_name=field_name,
        value=value,
        normalized_value=normalized_value or normalize(value),
        confidence=confidence,
        source=source,
        page_number=page_number,
        text_snippet=_snippet(text, match.start(), match.end()),
        metadata={},
    )


def _json_from_model_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    payload = json.loads(cleaned)
    return payload if isinstance(payload, dict) else {}


def _snippet(text: str, start: int, end: int) -> str:
    low = max(0, start - 80)
    high = min(len(text), end + 120)
    return re.sub(r"\s+", " ", text[low:high]).strip()


def _page_for_match(pages: list[str], needle: str) -> int | None:
    for index, page in enumerate(pages, start=1):
        if needle in page:
            return index
    return None


def _clean_parcel(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .,:;\n")
    value = re.split(r"\b(?:owner|proprietor|seller|date|registry|parcel|plot)\b", value, flags=re.I)[0]
    return value.strip(" .,:;-")


def _find_dates(text: str) -> Iterable[tuple[str, re.Match[str]]]:
    seen: set[str] = set()
    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            value = match.group(1)
            if value not in seen:
                seen.add(value)
                yield value, match


def normalize_date(value: str) -> str:
    candidates = ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"]
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return normalize(value)


def estimate_quality(text: str, content_type: str) -> float | None:
    if content_type.startswith("image/") and not text:
        return 0.35 if not settings.document_ai_enabled else None
    if not text:
        return 0.25
    unique_chars = len(set(text))
    length_score = min(len(text) / 1200, 1.0)
    char_score = min(unique_chars / 48, 1.0)
    return round(max(0.2, (length_score * 0.65) + (char_score * 0.35)), 2)

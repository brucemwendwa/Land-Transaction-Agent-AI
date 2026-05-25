from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domain.enums import (
    AnalysisStatus,
    CaseStatus,
    DocumentCategory,
    DocumentStatus,
    ReviewRole,
    RiskBand,
    RiskFactorCode,
    UserRole,
    VerificationStatus,
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
SHA256_PATTERN = r"^$|^[a-fA-F0-9]{64}$"


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def reject_nul_bytes(cls, value: Any) -> Any:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Input contains invalid null byte")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    clerk_user_id: str
    email: str
    full_name: str
    role: UserRole
    created_at: datetime


class CaseCreate(RequestModel):
    title: str = Field(min_length=2, max_length=255)
    buyer_name: str = Field(default="", max_length=255)
    seller_name: str = Field(default="", max_length=255)
    parcel_number_claimed: str = Field(default="", max_length=255)
    location_county: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=255)
    title_number: str = Field(default="", max_length=255)
    transaction_value: Decimal | None = Field(default=None, ge=0)
    preferred_language: str = Field(default="en", pattern="^(en|sw)$")
    payment_before_verification: bool = False


class CaseUpdate(RequestModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    buyer_name: str | None = Field(default=None, max_length=255)
    seller_name: str | None = Field(default=None, max_length=255)
    parcel_number_claimed: str | None = Field(default=None, max_length=255)
    location_county: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    title_number: str | None = Field(default=None, max_length=255)
    transaction_value: Decimal | None = Field(default=None, ge=0)
    preferred_language: str | None = Field(default=None, pattern="^(en|sw)$")
    payment_before_verification: bool | None = None


class ExtractedFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    field_name: str
    value: str
    normalized_value: str
    confidence: float
    source: str
    page_number: int | None
    bounding_box: dict[str, Any] | None
    text_snippet: str
    extraction_metadata: dict[str, Any]


class FieldCorrectionCreate(RequestModel):
    extracted_field_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    field_name: str = Field(min_length=1, max_length=120)
    corrected_value: str = Field(min_length=1, max_length=4000)
    reason: str = Field(default="", max_length=1000)


class FieldCorrectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extracted_field_id: str | None
    field_name: str
    ai_value: str
    corrected_value: str
    normalized_value: str
    reason: str
    metadata_json: dict[str, Any]
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    category: DocumentCategory
    filename: str
    content_type: str
    file_size: int
    sha256: str
    status: DocumentStatus
    extraction_status: str
    scan_status: str
    image_quality_score: float | None
    detected_document_type: str
    document_type_confidence: float | None
    extraction_warnings: list[dict[str, Any]]
    rejection_reason: str
    uploaded_at: datetime
    created_at: datetime
    extracted_fields: list[ExtractedFieldRead] = []
    field_corrections: list[FieldCorrectionRead] = []


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    buyer_name: str
    seller_name: str
    parcel_number_claimed: str
    location_county: str
    location: str
    title_number: str
    transaction_value: Decimal | None
    preferred_language: str
    payment_before_verification: bool
    status: CaseStatus
    risk_level: RiskBand | None
    risk_score: int | None
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentRead] = []


class SignedUploadRequest(RequestModel):
    case_id: str = Field(pattern=UUID_PATTERN)
    category: DocumentCategory
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    file_size: int = Field(gt=0)
    sha256: str = Field(default="", pattern=SHA256_PATTERN)
    consent_to_process: bool = False

    @model_validator(mode="after")
    def require_upload_consent(self) -> SignedUploadRequest:
        if not self.consent_to_process:
            raise ValueError("Consent is required before uploading land documents")
        return self


class SignedUploadResponse(BaseModel):
    document_id: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


class CompleteUploadRequest(RequestModel):
    document_id: str = Field(pattern=UUID_PATTERN)
    sha256: str = Field(default="", pattern=SHA256_PATTERN)


class ExtractionResult(BaseModel):
    document: DocumentRead
    extracted_fields: list[ExtractedFieldRead]
    verification_status: VerificationStatus


class DocumentReadUrlResponse(BaseModel):
    document_id: str
    read_url: str
    expires_in_minutes: int


class GazetteNoticeRead(BaseModel):
    source_name: str
    notice_title: str
    publication_date: str
    matched_keywords: list[str]
    snippet: str
    source_url: str
    confidence_score: float
    checked_at: str


class GazetteSourceResultRead(BaseModel):
    source_name: str
    status: str
    query_terms: list[str]
    notices: list[GazetteNoticeRead] = []
    error: str
    checked_at: str


class GazetteSearchResponse(BaseModel):
    status: str
    query_terms: list[str]
    results: list[GazetteNoticeRead]
    source_results: list[GazetteSourceResultRead]
    message: str
    checked_at: str
    disclaimer: str


class RiskFactorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: RiskFactorCode
    label: str
    severity: str
    points: int
    evidence: dict[str, Any]
    recommendation: str


class RiskAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    version: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskBand
    risk_summary: str
    risk_factors: list[dict[str, Any]]
    recommended_actions: list[str]
    missing_documents: list[dict[str, Any]]
    inconsistencies: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    result_json: dict[str, Any]
    created_at: datetime


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    status: AnalysisStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str
    agent_trace: dict[str, Any]


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    analysis_run_id: str
    score: int
    band: RiskBand
    verification_status: VerificationStatus
    language: str
    content: dict[str, Any]
    created_at: datetime
    risk_factors: list[RiskFactorRead] = []
    report_reference: str = ""
    download_url: str = ""
    is_stale: bool = False
    stale_reasons: list[str] = []


class ReviewRequestCreate(RequestModel):
    case_id: str = Field(pattern=UUID_PATTERN)
    reviewer_role: ReviewRole
    reviewer_email: EmailStr
    note: str = Field(default="", max_length=2000)


class ReviewRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    reviewer_role: ReviewRole
    reviewer_email: EmailStr
    note: str
    status: str
    created_at: datetime


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    title: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str | None
    case_id: str | None
    action: str
    target_type: str
    target_id: str
    ip_address: str
    metadata_json: dict[str, Any]
    created_at: datetime


class PricingSelectionRequest(RequestModel):
    plan_key: str = Field(pattern="^(starter|professional|firm)$")


class MpesaPaymentInitiateRequest(RequestModel):
    case_id: str = Field(pattern=UUID_PATTERN)
    amount: Decimal = Field(gt=0)
    phone_number: str = Field(min_length=10, max_length=20)
    purpose: str = Field(default="report_unlock", pattern="^(report_unlock|subscription|expert_review)$")


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str | None
    provider: str
    purpose: str
    amount: Decimal
    currency: str
    phone_number: str
    status: str
    provider_merchant_request_id: str
    provider_checkout_request_id: str
    provider_receipt_number: str
    result_code: str
    result_description: str
    paid_at: datetime | None
    created_at: datetime


class MpesaPaymentInitiateResponse(BaseModel):
    payment: PaymentRead | None = None
    status: str
    message: str


class MpesaCallbackResponse(BaseModel):
    status: str


class ReportGenerationRequest(RequestModel):
    accepted_legal_disclaimer: bool = False
    force_regenerate: bool = False

    @model_validator(mode="after")
    def require_legal_disclaimer_acceptance(self) -> ReportGenerationRequest:
        if not self.accepted_legal_disclaimer:
            raise ValueError("Legal disclaimer acceptance is required before generating a report")
        return self


class CaseAgentQuestionRequest(RequestModel):
    question: str = Field(min_length=3, max_length=1000)


class CaseAgentCitation(BaseModel):
    source_type: str
    title: str
    excerpt: str
    confidence: float | None = None
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseAgentAnswerResponse(BaseModel):
    answer: str
    citations: list[CaseAgentCitation]
    limitations: list[str]
    verification_status: str


class DeleteCaseResponse(BaseModel):
    status: str
    case_id: str
    deleted_documents: int
    deleted_reports: int


class HealthResponse(BaseModel):
    ok: bool
    service: str
    environment: str
    checks: dict[str, str] = Field(default_factory=dict)

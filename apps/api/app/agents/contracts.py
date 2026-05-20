from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import DocumentCategory, RiskBand, RiskFactorCode, VerificationStatus

AgentStatus = Literal["completed", "failed", "skipped"]
GazetteAgentStatus = Literal["checked_no_match", "matches_found", "not_checked", "failed"]
OfficialSearchAgentStatus = Literal["parsed", "missing", "failed"]


class EvidenceReference(BaseModel):
    document_id: str | None = None
    document_category: DocumentCategory | None = None
    field_name: str | None = None
    quote: str = ""
    source: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page_number: int | None = None
    bounding_box: dict[str, Any] | None = None
    text_snippet: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentFailure(BaseModel):
    code: str
    message: str
    retryable: bool = False


class AgentDecision(BaseModel):
    decision: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class AgentOutputBase(BaseModel):
    status: AgentStatus = "completed"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decisions: list[AgentDecision] = Field(default_factory=list)
    failure: AgentFailure | None = None


class DocumentDescriptor(BaseModel):
    id: str
    category: DocumentCategory
    filename: str
    content_type: str
    file_size: int = 0
    sha256: str = ""
    status: str = ""
    storage_uri: str = ""


class IntakeAgentInput(BaseModel):
    case_id: str
    title: str
    buyer_name: str = ""
    seller_name: str = ""
    parcel_number_claimed: str = ""
    location_county: str = ""
    location: str = ""
    title_number: str = ""
    preferred_language: str = "en"
    payment_before_verification: bool = False
    documents: list[DocumentDescriptor] = Field(default_factory=list)


class CaseProfile(BaseModel):
    case_id: str
    title: str
    buyer_name: str = ""
    seller_name: str = ""
    parcel_number_claimed: str = ""
    county: str = ""
    location: str = ""
    title_number: str = ""
    preferred_language: str = "en"
    payment_before_verification: bool = False
    missing_inputs: list[str] = Field(default_factory=list)
    uploaded_document_categories: list[DocumentCategory] = Field(default_factory=list)
    required_document_categories: list[DocumentCategory] = Field(default_factory=list)


class IntakeAgentOutput(AgentOutputBase):
    case_profile: CaseProfile


class ExtractedDocumentFields(BaseModel):
    document_id: str
    category: DocumentCategory
    filename: str
    document_type: str = ""
    parcel_number: str = ""
    title_number: str = ""
    registry: str = ""
    county: str = ""
    block: str = ""
    plot_number: str = ""
    owner_names: list[str] = Field(default_factory=list)
    seller_names: list[str] = Field(default_factory=list)
    buyer_names: list[str] = Field(default_factory=list)
    id_numbers: list[str] = Field(default_factory=list)
    kra_pin: str = ""
    document_dates: list[date] = Field(default_factory=list)
    transfer_dates: list[date] = Field(default_factory=list)
    search_dates: list[date] = Field(default_factory=list)
    land_size: str = ""
    encumbrances: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    charges: list[str] = Field(default_factory=list)
    suspicious_edit_signals: list[str] = Field(default_factory=list)
    signatures_present: bool | None = None
    seals_present: bool | None = None
    document_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_sources: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    failure: AgentFailure | None = None


class VisionExtractionAgentInput(BaseModel):
    case_profile: CaseProfile
    documents: list[DocumentDescriptor]


class VisionExtractionAgentOutput(AgentOutputBase):
    documents: list[ExtractedDocumentFields] = Field(default_factory=list)
    tool_statuses: dict[str, str] = Field(default_factory=dict)


class FieldMismatch(BaseModel):
    code: str
    label: str
    severity: Literal["low", "medium", "high", "critical"]
    values: list[str] = Field(default_factory=list)
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class MissingDocumentFinding(BaseModel):
    category: DocumentCategory
    explanation: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class DateSequenceFinding(BaseModel):
    code: str
    explanation: str
    dates: dict[str, list[date]] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ConsistencyAgentInput(BaseModel):
    case_profile: CaseProfile
    extracted_documents: list[ExtractedDocumentFields]


class ConsistencyAgentOutput(AgentOutputBase):
    missing_required_documents: list[MissingDocumentFinding] = Field(default_factory=list)
    mismatches: list[FieldMismatch] = Field(default_factory=list)
    suspicious_date_sequences: list[DateSequenceFinding] = Field(default_factory=list)
    old_search_certificate: bool = False
    mutation_survey_inconsistency: bool = False


class GazetteNotice(BaseModel):
    source: str
    date: str = ""
    title: str
    url: str
    snippet: str
    confidence: float = Field(ge=0.0, le=1.0)


class GazetteSearchAgentInput(BaseModel):
    case_profile: CaseProfile
    extracted_documents: list[ExtractedDocumentFields]


class GazetteSearchAgentOutput(AgentOutputBase):
    gazette_status: GazetteAgentStatus
    query_terms: list[str] = Field(default_factory=list)
    notices: list[GazetteNotice] = Field(default_factory=list)
    reason: str = ""


class ParsedOfficialSearchCertificate(BaseModel):
    document_id: str
    owner_names: list[str] = Field(default_factory=list)
    parcel_number: str = ""
    title_number: str = ""
    encumbrances: list[str] = Field(default_factory=list)
    date_issued: date | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class OfficialSearchAgentInput(BaseModel):
    case_profile: CaseProfile
    extracted_documents: list[ExtractedDocumentFields]


class OfficialSearchAgentOutput(AgentOutputBase):
    official_search_status: OfficialSearchAgentStatus
    verification_status: VerificationStatus
    certificate: ParsedOfficialSearchCertificate | None = None
    conflicts: list[FieldMismatch] = Field(default_factory=list)
    reason: str = ""


class AgentRiskFactor(BaseModel):
    code: RiskFactorCode
    label: str
    severity: str
    points: int
    evidence: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    recommendation: str


class RiskScoringAgentInput(BaseModel):
    case_profile: CaseProfile
    extracted_documents: list[ExtractedDocumentFields]
    consistency: ConsistencyAgentOutput
    gazette: GazetteSearchAgentOutput
    official_search: OfficialSearchAgentOutput
    duplicate_case_ids: list[str] = Field(default_factory=list)


class RiskScoringAgentOutput(AgentOutputBase):
    score: int = Field(ge=0, le=100)
    risk_level: RiskBand
    risk_factors: list[AgentRiskFactor] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)


class ReportAgentInput(BaseModel):
    case_profile: CaseProfile
    extracted_documents: list[ExtractedDocumentFields]
    consistency: ConsistencyAgentOutput
    gazette: GazetteSearchAgentOutput
    official_search: OfficialSearchAgentOutput
    risk: RiskScoringAgentOutput
    verification_status: VerificationStatus


class ReportAgentOutput(AgentOutputBase):
    content: dict[str, Any]
    generated_at: datetime


class LegalSafetyAgentInput(BaseModel):
    report_content: dict[str, Any]
    verification_status: VerificationStatus


class LegalSafetyAgentOutput(AgentOutputBase):
    approved: bool
    disclaimer: str
    blocked_claims: list[str] = Field(default_factory=list)
    sanitized_content: dict[str, Any]

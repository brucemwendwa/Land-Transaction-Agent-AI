from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
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


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def enum_column(enum_cls: type[Any]) -> Enum:
    return Enum(enum_cls, values_callable=lambda e: [item.value for item in e], native_enum=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_created_at", "created_at"),
        {"comment": "Companies, law firms, survey offices, or buyer groups that own users and cases."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Organization UUID.")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Human-readable organization name.")
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, comment="Stable URL/API slug.")

    users: Mapped[list[User]] = relationship(back_populates="organization")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_created_at", "created_at"),
        {"comment": "Authenticated people using Mradi wa Ardhi."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="User UUID.")
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="External Clerk user ID.")
    email: Mapped[str] = mapped_column(String(255), nullable=False, comment="User email address.")
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False, comment="User display name.")
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole), default=UserRole.BUYER, nullable=False, comment="Application authorization role."
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, comment="Optional owning organization."
    )

    organization: Mapped[Organization | None] = relationship(back_populates="users")
    cases: Mapped[list[LandCase]] = relationship(back_populates="owner")


class LandCase(Base, TimestampMixin):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_user_id", "user_id"),
        Index("ix_cases_parcel_number", "parcel_number"),
        Index("ix_cases_title_number", "title_number"),
        Index("ix_cases_created_at", "created_at"),
        Index("ix_cases_risk_level", "risk_level"),
        {"comment": "Land transaction due-diligence case. One case tracks one buyer/seller/parcel review."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Case UUID.")
    owner_user_id: Mapped[str] = mapped_column(
        "user_id", ForeignKey("users.id"), nullable=False, comment="User who owns the case."
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, comment="Organization that owns the case, when applicable."
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="Short case title shown in the dashboard.")
    location_county: Mapped[str] = mapped_column(
        "county", String(120), default="", nullable=False, comment="Kenyan county where the land is located."
    )
    location: Mapped[str] = mapped_column(
        String(255), default="", nullable=False, comment="More specific parcel locality, estate, ward, or registry location."
    )
    parcel_number_claimed: Mapped[str] = mapped_column(
        "parcel_number", String(255), default="", nullable=False, comment="Parcel number supplied by the buyer or documents."
    )
    title_number: Mapped[str] = mapped_column(
        String(255), default="", nullable=False, comment="Title number supplied by the buyer or extracted from title documents."
    )
    buyer_name: Mapped[str] = mapped_column(String(255), default="", nullable=False, comment="Primary buyer name.")
    seller_name: Mapped[str] = mapped_column(String(255), default="", nullable=False, comment="Primary seller name.")
    transaction_value: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True, comment="Stated transaction value in Kenyan shillings."
    )
    preferred_language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    payment_before_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        enum_column(CaseStatus),
        default=CaseStatus.DOCUMENTS_PENDING,
        nullable=False,
        comment="Workflow status for the case.",
    )
    risk_level: Mapped[RiskBand | None] = mapped_column(
        enum_column(RiskBand), nullable=True, comment="Latest summarized risk band from risk_analyses."
    )
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Latest summarized risk score from 0 to 100.")

    owner: Mapped[User] = relationship(back_populates="cases")
    participants: Mapped[list[CaseParticipant]] = relationship(back_populates="case", cascade="all,delete")
    documents: Mapped[list[Document]] = relationship(back_populates="case", cascade="all,delete")
    document_extractions: Mapped[list[DocumentExtraction]] = relationship(back_populates="case", cascade="all,delete")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="case", cascade="all,delete")
    risk_analysis_results: Mapped[list[RiskAnalysisResult]] = relationship(
        back_populates="case", cascade="all,delete"
    )
    gazette_searches: Mapped[list[GazetteSearch]] = relationship(back_populates="case", cascade="all,delete")
    gazette_search_results: Mapped[list[GazetteSearchResult]] = relationship(
        back_populates="case", cascade="all,delete"
    )
    risk_factors: Mapped[list[RiskFactor]] = relationship(back_populates="case", cascade="all,delete")
    reports: Mapped[list[Report]] = relationship(back_populates="case", cascade="all,delete")
    review_requests: Mapped[list[ReviewRequest]] = relationship(back_populates="case", cascade="all,delete")
    timeline_events: Mapped[list[TimelineEvent]] = relationship(back_populates="case", cascade="all,delete")
    notifications: Mapped[list[Notification]] = relationship(back_populates="case", cascade="all,delete")


class CaseParticipant(Base, TimestampMixin):
    __tablename__ = "case_participants"
    __table_args__ = (
        Index("ix_case_participants_case_id", "case_id"),
        Index("ix_case_participants_user_id", "user_id"),
        Index("ix_case_participants_created_at", "created_at"),
        {"comment": "People and organizations involved in a case, including buyers, sellers, advocates, and surveyors."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Participant UUID.")
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False, comment="Case this participant belongs to.")
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="Linked app user when available.")
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, comment="Linked organization when available."
    )
    role: Mapped[str] = mapped_column(String(80), nullable=False, comment="Participant role such as buyer, seller, advocate.")
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    id_number: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    kra_pin: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False, comment="Flexible participant metadata."
    )

    case: Mapped[LandCase] = relationship(back_populates="participants")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_case_id", "case_id"),
        Index("ix_documents_uploaded_by_user_id", "uploaded_by_user_id"),
        Index("ix_documents_uploaded_at", "uploaded_at"),
        Index("ix_documents_created_at", "created_at"),
        {"comment": "Uploaded files attached to a case, including titles, searches, IDs, and sale agreements."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Document UUID.")
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False, comment="Case this document belongs to.")
    uploaded_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="User who uploaded the document."
    )
    category: Mapped[DocumentCategory] = mapped_column(
        "document_type", enum_column(DocumentCategory), nullable=False, comment="Business document type."
    )
    filename: Mapped[str] = mapped_column("file_name", String(255), nullable=False, comment="Original uploaded file name.")
    file_url: Mapped[str] = mapped_column(
        String(1000), default="", nullable=False, comment="Legacy URL cache; production responses must not expose file URLs."
    )
    storage_uri: Mapped[str] = mapped_column(
        "storage_key", String(500), nullable=False, comment="Private storage key/URI used by the storage adapter."
    )
    content_type: Mapped[str] = mapped_column("mime_type", String(120), nullable=False, comment="Uploaded MIME type.")
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="File size in bytes.")
    sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False, comment="SHA-256 digest for integrity checks.")
    status: Mapped[DocumentStatus] = mapped_column(
        "upload_status",
        enum_column(DocumentStatus),
        default=DocumentStatus.UPLOADING,
        nullable=False,
        comment="Upload and malware-scan status.",
    )
    extraction_status: Mapped[str] = mapped_column(
        String(60), default="pending", nullable=False, comment="Latest extraction workflow status for the document."
    )
    scan_status: Mapped[str] = mapped_column(String(60), default="pending", nullable=False)
    image_quality_score: Mapped[float | None] = mapped_column(
        "quality_score", Float, nullable=True, comment="Image/OCR quality score from 0 to 1 when available."
    )
    detected_document_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    document_type_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    rejection_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="Timestamp when the upload record was created."
    )

    case: Mapped[LandCase] = relationship(back_populates="documents")
    extraction_runs: Mapped[list[DocumentExtraction]] = relationship(
        back_populates="document", cascade="all,delete"
    )
    extracted_fields: Mapped[list[ExtractedField]] = relationship(
        back_populates="document", cascade="all,delete"
    )
    field_corrections: Mapped[list[FieldCorrection]] = relationship(
        back_populates="document", cascade="all,delete"
    )


class DocumentExtraction(Base, TimestampMixin):
    __tablename__ = "document_extractions"
    __table_args__ = (
        Index("ix_document_extractions_case_id", "case_id"),
        Index("ix_document_extractions_document_id", "document_id"),
        Index("ix_document_extractions_created_at", "created_at"),
        {"comment": "One OCR/AI extraction run for a document, with model metadata and raw output."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Extraction run UUID.")
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False, comment="Case being extracted.")
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, comment="Document being extracted.")
    status: Mapped[str] = mapped_column(String(60), default="pending", nullable=False, comment="Extraction run status.")
    engine_version: Mapped[str] = mapped_column(String(80), default="", nullable=False, comment="Extraction pipeline version.")
    model_version: Mapped[str] = mapped_column(String(120), default="", nullable=False, comment="OCR/vision model version.")
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False, comment="Raw OCR text, when small enough to persist.")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False, comment="Structured raw model output.")
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    case: Mapped[LandCase] = relationship(back_populates="document_extractions")
    document: Mapped[Document] = relationship(back_populates="extraction_runs")
    extracted_fields: Mapped[list[ExtractedField]] = relationship(back_populates="document_extraction")


class ExtractedField(Base, TimestampMixin):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        Index("ix_extracted_fields_source_document_id", "source_document_id"),
        Index("ix_extracted_fields_document_extraction_id", "document_extraction_id"),
        Index("ix_extracted_fields_created_at", "created_at"),
        {"comment": "Normalized facts extracted from uploaded documents, with confidence and source evidence."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Extracted field UUID.")
    document_id: Mapped[str] = mapped_column(
        "source_document_id", ForeignKey("documents.id"), nullable=False, comment="Document that supplied the field."
    )
    document_extraction_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_extractions.id"), nullable=True, comment="Extraction run that produced the field."
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False, comment="Canonical extracted field name.")
    value: Mapped[str] = mapped_column("field_value", Text, nullable=False, comment="Extracted field value.")
    normalized_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="deterministic", nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    text_snippet: Mapped[str] = mapped_column(
        "raw_text_snippet", Text, default="", nullable=False, comment="Short source text snippet supporting the value."
    )
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    document: Mapped[Document] = relationship(back_populates="extracted_fields")
    document_extraction: Mapped[DocumentExtraction | None] = relationship(back_populates="extracted_fields")
    corrections: Mapped[list[FieldCorrection]] = relationship(back_populates="extracted_field")


class FieldCorrection(Base, TimestampMixin):
    __tablename__ = "user_field_corrections"
    __table_args__ = (
        Index("ix_user_field_corrections_source_document_id", "source_document_id"),
        Index("ix_user_field_corrections_user_id", "user_id"),
        Index("ix_user_field_corrections_created_at", "created_at"),
        {"comment": "Human corrections to extracted_fields; corrections are preserved instead of mutating AI output."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Correction UUID.")
    document_id: Mapped[str] = mapped_column(
        "source_document_id", ForeignKey("documents.id"), nullable=False, comment="Document whose field was corrected."
    )
    extracted_field_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_fields.id"), nullable=True)
    corrected_by_user_id: Mapped[str] = mapped_column(
        "user_id", ForeignKey("users.id"), nullable=False, comment="User who made the correction."
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    ai_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrected_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    document: Mapped[Document] = relationship(back_populates="field_corrections")
    extracted_field: Mapped[ExtractedField | None] = relationship(back_populates="corrections")


class NormalizedParcel(Base, TimestampMixin):
    __tablename__ = "normalized_parcels"
    __table_args__ = (
        Index("ix_normalized_parcels_case_id", "case_id"),
        Index("ix_normalized_parcels_parcel_number", "parcel_number"),
        Index("ix_normalized_parcels_created_at", "created_at"),
        {"comment": "Parsed parcel identifiers normalized from case input and source documents."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    parcel_number: Mapped[str] = mapped_column(String(255), nullable=False)
    land_registry: Mapped[str] = mapped_column("registry", String(255), default="", nullable=False)
    section: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    block: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    plot: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)


class NormalizedParty(Base, TimestampMixin):
    __tablename__ = "normalized_parties"
    __table_args__ = (
        Index("ix_normalized_parties_case_id", "case_id"),
        Index("ix_normalized_parties_created_at", "created_at"),
        {"comment": "Parsed buyer, seller, witness, advocate, and owner identities normalized from documents."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    id_number: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    kra_pin: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)


class AnalysisRun(Base, TimestampMixin):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_case_id", "case_id"),
        Index("ix_analysis_runs_created_at", "created_at"),
        {"comment": "End-to-end agent orchestration runs for a case."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        enum_column(AnalysisStatus), default=AnalysisStatus.QUEUED, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agent_trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="analysis_runs")


class VerificationAttempt(Base, TimestampMixin):
    __tablename__ = "verification_attempts"
    __table_args__ = (
        Index("ix_verification_attempts_case_id", "case_id"),
        Index("ix_verification_attempts_created_at", "created_at"),
        {"comment": "Attempts to verify case facts against external or official sources."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    adapter_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(enum_column(VerificationStatus), nullable=False)
    query: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)


class GazetteSearch(Base, TimestampMixin):
    __tablename__ = "gazette_searches"
    __table_args__ = (
        Index("ix_gazette_searches_case_id", "case_id"),
        Index("ix_gazette_searches_user_id", "user_id"),
        Index("ix_gazette_searches_created_at", "created_at"),
        {"comment": "Gazette search requests made for a case before individual results are stored."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False, comment="Case being searched.")
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="User who initiated the search.")
    query_terms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False, comment="Terms sent to Gazette sources.")
    county: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    parcel_number: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    title_number: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="completed", nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    searched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="gazette_searches")
    results: Mapped[list[GazetteSearchResult]] = relationship(back_populates="gazette_search", cascade="all,delete")


class GazetteSearchResult(Base, TimestampMixin):
    __tablename__ = "gazette_results"
    __table_args__ = (
        Index("ix_gazette_results_case_id", "case_id"),
        Index("ix_gazette_results_gazette_search_id", "gazette_search_id"),
        Index("ix_gazette_results_created_at", "created_at"),
        {"comment": "Individual public Gazette notices returned by gazette_searches."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    gazette_search_id: Mapped[str | None] = mapped_column(ForeignKey("gazette_searches.id"), nullable=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    notice_title: Mapped[str] = mapped_column(String(500), nullable=False)
    publication_date: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="gazette_search_results")
    gazette_search: Mapped[GazetteSearch | None] = relationship(back_populates="results")


class RiskAnalysisResult(Base, TimestampMixin):
    __tablename__ = "risk_analyses"
    __table_args__ = (
        Index("ix_risk_analyses_case_id", "case_id"),
        Index("ix_risk_analyses_level", "level"),
        Index("ix_risk_analyses_created_at", "created_at"),
        {"comment": "Versioned risk scoring output for a case."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id, comment="Risk analysis UUID.")
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False, comment="Case being scored.")
    version: Mapped[str] = mapped_column("model_version", String(80), nullable=False, comment="Risk model version.")
    engine_version: Mapped[str] = mapped_column(
        String(80), default="mradi-risk-engine-v1", nullable=False, comment="Risk engine implementation version."
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="Risk score from 0 to 100.")
    band: Mapped[RiskBand] = mapped_column("level", enum_column(RiskBand), nullable=False, comment="Risk band.")
    summary: Mapped[str] = mapped_column(Text, nullable=False, comment="Buyer-friendly risk summary.")
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="risk_analysis_results")
    risk_factors: Mapped[list[RiskFactor]] = relationship(back_populates="risk_analysis")


class RiskFactor(Base, TimestampMixin):
    __tablename__ = "risk_factors"
    __table_args__ = (
        Index("ix_risk_factors_case_id", "case_id"),
        Index("ix_risk_factors_risk_analysis_id", "risk_analysis_id"),
        Index("ix_risk_factors_created_at", "created_at"),
        {"comment": "Explainable factors contributing to a risk_analyses score."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    risk_analysis_id: Mapped[str | None] = mapped_column(ForeignKey("risk_analyses.id"), nullable=True)
    code: Mapped[RiskFactorCode] = mapped_column(enum_column(RiskFactorCode), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="risk_factors")
    risk_analysis: Mapped[RiskAnalysisResult | None] = relationship(back_populates="risk_factors")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_case_id", "case_id"),
        Index("ix_reports_created_at", "created_at"),
        {"comment": "Generated buyer-facing due-diligence reports."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[RiskBand] = mapped_column(enum_column(RiskBand), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus), nullable=False
    )
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    pdf_storage_uri: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="reports")


class ReviewRequest(Base, TimestampMixin):
    __tablename__ = "expert_reviews"
    __table_args__ = (
        Index("ix_expert_reviews_case_id", "case_id"),
        Index("ix_expert_reviews_user_id", "user_id"),
        Index("ix_expert_reviews_created_at", "created_at"),
        {"comment": "Manual expert review requests for advocates, surveyors, and other professionals."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column("user_id", ForeignKey("users.id"), nullable=False)
    reviewer_role: Mapped[ReviewRole] = mapped_column(enum_column(ReviewRole), nullable=False)
    reviewer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="requested", nullable=False)
    review_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="review_requests")


class TimelineEvent(Base, TimestampMixin):
    __tablename__ = "timeline_events"
    __table_args__ = (
        Index("ix_timeline_events_case_id", "case_id"),
        Index("ix_timeline_events_created_at", "created_at"),
        {"comment": "Chronological case activity used for the timeline UI."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    case: Mapped[LandCase] = relationship(back_populates="timeline_events")


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_case_id", "case_id"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        {"comment": "Append-only audit trail for user and system actions."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column("actor_id", ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column("entity_type", String(80), nullable=False)
    target_id: Mapped[str] = mapped_column("entity_id", String(120), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class PricingPlanSelection(Base, TimestampMixin):
    __tablename__ = "payments_optional"
    __table_args__ = (
        Index("ix_payments_optional_user_id", "user_id"),
        Index("ix_payments_optional_case_id", "case_id"),
        Index("ix_payments_optional_created_at", "created_at"),
        {"comment": "Optional billing/payment records; safe to leave unused until payments are enabled."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    plan_key: Mapped[str] = mapped_column(String(80), nullable=False)
    billing_status: Mapped[str] = mapped_column(String(80), default="selected", nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="KES", nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_case_id", "case_id"),
        Index("ix_notifications_created_at", "created_at"),
        {"comment": "In-app and email notification records for case events and review updates."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    notification_type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    channel: Mapped[str] = mapped_column(String(40), default="in_app", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="unread", nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    case: Mapped[LandCase | None] = relationship(back_populates="notifications")


class ApiKeyOptional(Base, TimestampMixin):
    __tablename__ = "api_keys_optional"
    __table_args__ = (
        Index("ix_api_keys_optional_user_id", "user_id"),
        Index("ix_api_keys_optional_key_prefix", "key_prefix"),
        Index("ix_api_keys_optional_created_at", "created_at"),
        {"comment": "Optional hashed API keys for future partner/API access."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class AgentAuditEvent(Base, TimestampMixin):
    __tablename__ = "agent_audit_events"
    __table_args__ = (
        Index("ix_agent_audit_events_case_id", "case_id"),
        Index("ix_agent_audit_events_created_at", "created_at"),
        {"comment": "Agent-level prompts, output summaries, and model traces for governance."},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)


UserFieldCorrection = FieldCorrection
GazetteResult = GazetteSearchResult
RiskAnalysis = RiskAnalysisResult
ExpertReview = ReviewRequest
PaymentOptional = PricingPlanSelection

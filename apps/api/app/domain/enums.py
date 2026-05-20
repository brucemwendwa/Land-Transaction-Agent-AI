from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    BUYER = "buyer"
    ADVOCATE = "advocate"
    SURVEYOR = "surveyor"
    ADMIN = "admin"


class CaseStatus(StrEnum):
    DRAFT = "draft"
    DOCUMENTS_PENDING = "documents_pending"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYZING = "analyzing"
    REPORT_READY = "report_ready"
    MANUAL_REVIEW = "manual_review"
    CLOSED = "closed"


class DocumentCategory(StrEnum):
    TITLE_DEED = "title_deed"
    SALE_AGREEMENT = "sale_agreement"
    NATIONAL_ID_OR_PASSPORT = "national_id_or_passport"
    KRA_PIN_CERTIFICATE = "kra_pin_certificate"
    LAND_SEARCH_CERTIFICATE = "land_search_certificate"
    MUTATION_FORM = "mutation_form"
    SURVEY_MAP = "survey_map"
    CONSENT_TO_TRANSFER = "consent_to_transfer"
    RATES_CLEARANCE_CERTIFICATE = "rates_clearance_certificate"
    LAND_RENT_CLEARANCE_CERTIFICATE = "land_rent_clearance_certificate"
    SPOUSAL_CONSENT = "spousal_consent"
    POWER_OF_ATTORNEY = "power_of_attorney"
    KENYA_GAZETTE_NOTICE = "kenya_gazette_notice"
    OTHER_SUPPORTING_DOCUMENT = "other_supporting_document"


class DocumentStatus(StrEnum):
    UPLOADING = "uploading"
    QUARANTINED = "quarantined"
    CLEAN = "clean"
    REJECTED = "rejected"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    CONFLICT_FOUND = "conflict_found"
    NOT_CHECKED = "not_checked"
    NOT_VERIFIED_FROM_OFFICIAL_SOURCE = "not_verified_from_official_source"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactorCode(StrEnum):
    MISSING_TITLE_DEED = "missing_title_deed"
    MISSING_PARCEL_OR_TITLE_NUMBER = "missing_parcel_or_title_number"
    PARCEL_NUMBER_MISMATCH = "parcel_number_mismatch"
    SELLER_NAME_MISMATCH = "seller_name_mismatch"
    ID_MISMATCH = "id_mismatch"
    MISSING_OFFICIAL_LAND_SEARCH = "missing_official_land_search"
    STALE_SEARCH_CERTIFICATE = "stale_search_certificate"
    SALE_AGREEMENT_BEFORE_SEARCH = "sale_agreement_before_search"
    MISSING_CONSENT_TO_TRANSFER = "missing_consent_to_transfer"
    MISSING_SPOUSAL_CONSENT = "missing_spousal_consent"
    GAZETTE_NOTICE_CONFLICT = "gazette_notice_conflict"
    CAUTION_RESTRICTION_CHARGE = "caution_restriction_charge"
    MULTIPLE_OWNERS_ONE_SELLER = "multiple_owners_one_seller"
    POWER_OF_ATTORNEY_UNVERIFIED = "power_of_attorney_unverified"
    POOR_IMAGE_QUALITY = "poor_image_quality"
    SUSPICIOUS_DOCUMENT_EDITS = "suspicious_document_edits"
    LOW_DOCUMENT_CONFIDENCE = "low_document_confidence"
    MISSING_KRA_PIN = "missing_kra_pin"
    MISSING_WITNESS_OR_ADVOCATE_DETAILS = "missing_witness_or_advocate_details"
    MISSING_RENT_OR_RATES_CLEARANCE = "missing_rent_or_rates_clearance"
    BOUNDARY_OR_MUTATION_INCONSISTENCY = "boundary_or_mutation_inconsistency"
    PAYMENT_BEFORE_VERIFICATION = "payment_before_verification"
    DUPLICATE_PARCEL_NUMBER = "duplicate_parcel_number"


class ReviewRole(StrEnum):
    ADVOCATE = "advocate"
    SURVEYOR = "surveyor"
    SITE_VISIT = "site_visit"
    BOUNDARY_VERIFICATION = "boundary_verification"
    OFFICIAL_SEARCH_ASSISTANCE = "official_search_assistance"

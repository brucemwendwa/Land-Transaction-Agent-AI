export const documentCategories = [
  "title_deed",
  "sale_agreement",
  "national_id_or_passport",
  "kra_pin_certificate",
  "land_search_certificate",
  "mutation_form",
  "survey_map",
  "consent_to_transfer",
  "rates_clearance_certificate",
  "land_rent_clearance_certificate",
  "spousal_consent",
  "power_of_attorney",
  "kenya_gazette_notice",
  "other_supporting_document"
] as const;

export type DocumentCategory = (typeof documentCategories)[number];

export type CaseStatus =
  | "draft"
  | "documents_pending"
  | "ready_for_analysis"
  | "analyzing"
  | "report_ready"
  | "manual_review"
  | "closed";

export type DocumentStatus =
  | "uploading"
  | "quarantined"
  | "clean"
  | "rejected"
  | "extracting"
  | "extracted"
  | "needs_review";

export type VerificationStatus =
  | "verified"
  | "conflict_found"
  | "not_checked"
  | "not_verified_from_official_source"
  | "manual_review_required"
  | "adapter_unavailable";

export type RiskBand = "low" | "medium" | "high" | "critical";

export type UserRole = "buyer" | "advocate" | "surveyor" | "admin";

export interface ExtractedField {
  id: string;
  document_id: string;
  field_name: string;
  value: string;
  normalized_value: string;
  confidence: number;
  source: string;
  page_number: number | null;
  bounding_box: Record<string, unknown> | null;
  text_snippet: string;
  extraction_metadata: Record<string, unknown>;
}

export interface FieldCorrection {
  id: string;
  document_id: string;
  extracted_field_id: string | null;
  field_name: string;
  ai_value: string;
  corrected_value: string;
  normalized_value: string;
  reason: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type RiskFactorCode =
  | "missing_title_deed"
  | "missing_parcel_or_title_number"
  | "parcel_number_mismatch"
  | "seller_name_mismatch"
  | "id_mismatch"
  | "missing_official_land_search"
  | "stale_search_certificate"
  | "sale_agreement_before_search"
  | "missing_consent_to_transfer"
  | "missing_spousal_consent"
  | "gazette_notice_conflict"
  | "caution_restriction_charge"
  | "multiple_owners_one_seller"
  | "power_of_attorney_unverified"
  | "poor_image_quality"
  | "suspicious_document_edits"
  | "low_document_confidence"
  | "missing_kra_pin"
  | "missing_witness_or_advocate_details"
  | "missing_rent_or_rates_clearance"
  | "boundary_or_mutation_inconsistency"
  | "payment_before_verification"
  | "duplicate_parcel_number";

export interface RiskReportSummary {
  caseId: string;
  score: number;
  band: RiskBand;
  verificationStatus: VerificationStatus;
  title: string;
  generatedAt: string;
}

export interface RiskAnalysisResult {
  id: string;
  case_id: string;
  version: string;
  risk_score: number;
  risk_level: RiskBand;
  risk_summary: string;
  risk_factors: Array<Record<string, unknown>>;
  recommended_actions: string[];
  missing_documents: Array<Record<string, unknown>>;
  inconsistencies: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  result_json: Record<string, unknown>;
  created_at: string;
}

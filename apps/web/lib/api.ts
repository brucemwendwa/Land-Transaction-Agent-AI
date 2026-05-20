import type { DocumentCategory, RiskBand, VerificationStatus } from "@mradi/contracts";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface ApiDocument {
  id: string;
  case_id: string;
  category: DocumentCategory;
  filename: string;
  content_type: string;
  file_size: number;
  sha256: string;
  status: string;
  scan_status: string;
  image_quality_score: number | null;
  rejection_reason: string;
  created_at: string;
  extracted_fields: Array<{
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
  }>;
  field_corrections: Array<{
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
  }>;
  detected_document_type: string;
  document_type_confidence: number | null;
  extraction_warnings: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
}

export interface ApiCase {
  id: string;
  title: string;
  buyer_name: string;
  seller_name: string;
  parcel_number_claimed: string;
  location_county: string;
  location: string;
  title_number: string;
  preferred_language: string;
  payment_before_verification: boolean;
  status: string;
  risk_level: RiskBand | null;
  risk_score: number | null;
  created_at: string;
  updated_at: string;
  documents: ApiDocument[];
}

export interface ApiRiskFactor {
  code: string;
  label: string;
  severity: string;
  points: number;
  evidence: Record<string, unknown>;
  evidence_refs?: Array<Record<string, unknown>>;
  trust_evidence?: TrustEvidenceRow | null;
  recommendation: string;
}

export interface TrustEvidenceRow {
  risk_code: string;
  risk_label: string;
  what_detected: string;
  document_caused: string;
  document_id: string | null;
  extracted_value: string;
  compared_value: string;
  confidence_score: number | null;
  recommended_action: string;
}

export interface VerificationStatusLabel {
  code: string;
  label: string;
  applies: boolean;
  status: string;
  tone: string;
  explanation: string;
}

export interface BeforeDepositWarning {
  code: string;
  label: string;
  severity: string;
  triggered: boolean;
  explanation: string;
  recommended_action: string;
}

export interface HumanReviewOption {
  role: "advocate" | "surveyor" | "site_visit" | "boundary_verification" | "official_search_assistance";
  label: string;
  recommended: boolean;
  reason: string;
}

export interface ApiReport {
  id: string;
  case_id: string;
  analysis_run_id: string;
  score: number;
  band: RiskBand;
  verification_status: VerificationStatus;
  language: string;
  content: {
    schema_version?: string;
    brand?: string;
    report_id?: string;
    warning?: string;
    title: string;
    generated_at?: string;
    summary: {
      score: number;
      band: string;
      verification_status: string;
      plain_english: string;
      kiswahili: string;
    };
    case_summary?: Record<string, unknown>;
    buyer_seller_details?: Record<string, unknown>;
    parcel_title_details?: Record<string, unknown>;
    documents_reviewed?: Array<Record<string, unknown>>;
    extracted_information?: Array<{
      document_id?: string;
      document_label?: string;
      extraction_confidence?: number | null;
      document_quality_score?: number | null;
      fields?: Array<{ name: string; value: unknown; confidence?: number | null; source?: string; status_labels?: string[] }>;
    }>;
    missing_documents?: Array<Record<string, unknown>>;
    inconsistencies_found?: Array<Record<string, unknown>>;
    gazette_search_results?: Record<string, unknown> & {
      notices?: Array<Record<string, unknown>>;
      query_terms?: string[];
    };
    gazette_risk_intelligence?: Record<string, unknown> & {
      status?: string;
      query_terms?: string[];
      searched_fields?: string[];
      recommended_action?: string;
    };
    official_search_certificate_review?: Record<string, unknown> & {
      certificate?: Record<string, unknown> | null;
      conflicts?: Array<Record<string, unknown>>;
    };
    search_certificate_intelligence?: Record<string, unknown>;
    verification_status_labels?: VerificationStatusLabel[];
    before_deposit_warnings?: BeforeDepositWarning[];
    trust_evidence_panel?: TrustEvidenceRow[];
    confidence_scores?: {
      documents: Array<Record<string, unknown>>;
      fields: Array<Record<string, unknown>>;
    };
    human_review_workflow?: HumanReviewOption[];
    risk_score?: number;
    risk_level?: string;
    risk_factors: ApiRiskFactor[];
    detailed_risk_factors?: ApiRiskFactor[];
    recommended_next_steps: string[];
    plain_english_explanation?: string;
    kiswahili_summary?: string;
    kiswahili_summaries?: {
      risk_report: string;
      warnings: string;
      next_steps: string;
      missing_documents: string;
    };
    legal_disclaimer: string;
    appendix_evidence_references?: Array<Record<string, unknown>>;
  };
  created_at: string;
  risk_factors: ApiRiskFactor[];
  report_reference: string;
  download_url: string;
  is_stale: boolean;
  stale_reasons: string[];
}

export interface ApiCaseAgentAnswer {
  answer: string;
  citations: Array<{
    source_type: string;
    title: string;
    excerpt: string;
    confidence: number | null;
    document_id: string | null;
    metadata: Record<string, unknown>;
  }>;
  limitations: string[];
  verification_status: string;
}

export interface ApiGazetteSearch {
  status: "checked_no_match" | "checked_match_found" | "search_failed" | "not_configured" | "manual_review_required";
  query_terms: string[];
  results: Array<{
    source_name: string;
    notice_title: string;
    publication_date: string;
    matched_keywords: string[];
    snippet: string;
    source_url: string;
    confidence_score: number;
    checked_at: string;
  }>;
  source_results: Array<{
    source_name: string;
    status: string;
    query_terms: string[];
    error: string;
    checked_at: string;
  }>;
  message: string;
  checked_at: string;
  disclaimer: string;
}

export async function apiFetch<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("accept", "application/json");
  if (!(init?.body instanceof FormData)) headers.set("content-type", "application/json");
  if (token) headers.set("authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response.json() as Promise<T>;
}

export function apiUrl(path: string) {
  return `${API_URL}${path}`;
}

async function errorMessage(response: Response) {
  const fallback = `Request failed with ${response.status}`;
  const text = await response.text();
  if (!text) return fallback;
  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = payload.detail ?? payload.message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) return String(item.msg);
          return "";
        })
        .filter(Boolean)
        .join(" ");
    }
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
  } catch {
    return text;
  }
  return text || fallback;
}

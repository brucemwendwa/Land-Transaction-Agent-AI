import type { Page, Route } from "@playwright/test";
import type { ApiCase, ApiDocument, ApiReport, PaymentRead, ReviewRequest } from "@/lib/api";

type TimelineEvent = {
  id: string;
  event_type: string;
  title: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

type PendingUpload = {
  document: ApiDocument;
};

export type MockPaymentPollStatus = "initiated" | "pending" | "failed" | "successful";

export type MockMradiApiState = {
  adminForbidden: boolean;
  cases: ApiCase[];
  extractionConfigured: boolean;
  gated: boolean;
  inaccessibleCaseIds: Set<string>;
  mpesaConfigured: boolean;
  paymentPollStatus: MockPaymentPollStatus;
  paymentSuccessful: boolean;
  pendingUploads: Record<string, PendingUpload>;
  reportAvailable: boolean;
  reports: Record<string, ApiReport>;
  reviews: ReviewRequest[];
  timelineEvents: Record<string, TimelineEvent[]>;
};

type MockMradiApiOptions = Partial<
  Pick<
    MockMradiApiState,
    | "adminForbidden"
    | "cases"
    | "extractionConfigured"
    | "gated"
    | "mpesaConfigured"
    | "paymentPollStatus"
    | "paymentSuccessful"
    | "reportAvailable"
    | "reviews"
  >
> & {
  inaccessibleCaseIds?: string[];
  reports?: Record<string, ApiReport>;
  timelineEvents?: Record<string, TimelineEvent[]>;
};

const now = "2026-05-25T08:00:00";

export function createMockMradiApiState(options: MockMradiApiOptions = {}): MockMradiApiState {
  const cases = options.cases ?? [makeCase({ documents: [makeDocument()] })];
  return {
    adminForbidden: options.adminForbidden ?? false,
    cases,
    extractionConfigured: options.extractionConfigured ?? true,
    gated: options.gated ?? false,
    inaccessibleCaseIds: new Set(options.inaccessibleCaseIds ?? []),
    mpesaConfigured: options.mpesaConfigured ?? true,
    paymentPollStatus: options.paymentPollStatus ?? "successful",
    paymentSuccessful: options.paymentSuccessful ?? false,
    pendingUploads: {},
    reportAvailable: options.reportAvailable ?? false,
    reports: options.reports ?? {},
    reviews: options.reviews ?? [],
    timelineEvents: options.timelineEvents ?? {},
  };
}

export async function mockMradiApi(page: Page, options: MockMradiApiOptions = {}) {
  const state = createMockMradiApiState(options);

  await page.route("**/mock-upload/**", async (route) => {
    await route.fulfill({ status: 200, headers: corsHeaders(), body: "" });
  });

  await page.route(/http:\/\/(localhost|127\.0\.0\.1):8000\/.*/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders(), body: "" });
      return;
    }

    if (request.method() === "PUT") {
      await route.fulfill({ status: 200, headers: corsHeaders(), body: "" });
      return;
    }

    if (path === "/cases" && request.method() === "GET") {
      await json(route, state.cases);
      return;
    }

    if (path === "/cases" && request.method() === "POST") {
      const payload = request.postDataJSON() as Partial<ApiCase>;
      const landCase = makeCase({
        id: `case-${state.cases.length + 1}`,
        title: String(payload.title || "Untitled land case"),
        buyer_name: String(payload.buyer_name || ""),
        seller_name: String(payload.seller_name || ""),
        parcel_number_claimed: String(payload.parcel_number_claimed || ""),
        location_county: String(payload.location_county || ""),
        preferred_language: String(payload.preferred_language || "en"),
        payment_before_verification: Boolean(payload.payment_before_verification),
        documents: []
      });
      state.cases.push(landCase);
      state.timelineEvents[landCase.id] = [timelineEvent("case_created", "Case created")];
      await json(route, landCase);
      return;
    }

    const caseMatch = path.match(/^\/cases\/([^/]+)$/);
    if (caseMatch && request.method() === "GET") {
      const caseId = caseMatch[1];
      if (state.inaccessibleCaseIds.has(caseId)) {
        await json(route, { detail: "Case is not accessible" }, 403);
        return;
      }
      const landCase = findCase(state, caseId);
      await json(route, landCase ?? { detail: "Case not found" }, landCase ? 200 : 404);
      return;
    }

    const timelineMatch = path.match(/^\/cases\/([^/]+)\/timeline$/);
    if (timelineMatch && request.method() === "GET") {
      await json(route, state.timelineEvents[timelineMatch[1]] ?? []);
      return;
    }

    if (path === "/uploads/signed-url" && request.method() === "POST") {
      const payload = request.postDataJSON() as {
        case_id: string;
        category: ApiDocument["category"];
        filename: string;
        content_type: string;
        file_size: number;
        sha256: string;
      };
      const documentId = `doc-${Object.keys(state.pendingUploads).length + 1}`;
      state.pendingUploads[documentId] = {
        document: makeDocument({
          id: documentId,
          case_id: payload.case_id,
          category: payload.category,
          filename: payload.filename,
          content_type: payload.content_type,
          file_size: payload.file_size,
          sha256: payload.sha256
        })
      };
      await json(route, {
        document_id: documentId,
        upload_url: `http://127.0.0.1:3002/mock-upload/${documentId}`,
        method: "PUT",
        headers: { "content-type": payload.content_type },
        expires_at: "2026-05-25T08:15:00"
      });
      return;
    }

    if (path === "/uploads/complete" && request.method() === "POST") {
      const payload = request.postDataJSON() as { document_id: string };
      const pending = state.pendingUploads[payload.document_id];
      if (!pending) {
        await json(route, { detail: "Pending upload not found" }, 404);
        return;
      }
      const landCase = findCase(state, pending.document.case_id);
      if (landCase) {
        landCase.documents = [...landCase.documents, pending.document];
        landCase.status = "ready_for_analysis";
      }
      delete state.pendingUploads[payload.document_id];
      await json(route, { document_id: payload.document_id, status: "clean", scan_status: "not_configured" });
      return;
    }

    const extractionMatch = path.match(/^\/documents\/([^/]+)\/extract$/);
    if (extractionMatch && request.method() === "POST") {
      const documentId = extractionMatch[1];
      const document = state.cases.flatMap((landCase) => landCase.documents).find((item) => item.id === documentId);
      if (!document) {
        await json(route, { detail: "Document not found" }, 404);
        return;
      }
      const extracted = makeDocument({
        ...document,
        extraction_warnings: state.extractionConfigured
          ? []
          : [
              {
                code: "provider_not_configured",
                severity: "warning",
                message: "No OCR or vision extraction provider is configured for this file type. Manual review is required."
              }
            ],
        extracted_fields: state.extractionConfigured
          ? [
              {
                id: "field-1",
                document_id: document.id,
                field_name: "parcel_number",
                value: "LR 209/1234",
                normalized_value: "lr2091234",
                confidence: 0.91,
                source: "ai_extracted",
                page_number: 1,
                bounding_box: null,
                text_snippet: "Parcel LR 209/1234",
                extraction_metadata: { provider_status: "completed" }
              }
            ]
          : []
      });
      replaceDocument(state, extracted);
      await json(route, { document: extracted, extracted_fields: extracted.extracted_fields, verification_status: "not_checked" });
      return;
    }

    const analysisMatch = path.match(/^\/cases\/([^/]+)\/analysis$/);
    if (analysisMatch && request.method() === "POST") {
      const report = reportForCase(state, analysisMatch[1]);
      state.reports[analysisMatch[1]] = report;
      state.reportAvailable = true;
      await json(route, report);
      return;
    }

    const gazetteMatch = path.match(/^\/api\/cases\/([^/]+)\/gazette-search$/);
    if (gazetteMatch && request.method() === "POST") {
      await json(route, {
        status: "not_configured",
        query_terms: ["LR 209/1234", "Kajiado"],
        results: [],
        source_results: [
          {
            source_name: "Kenya Gazette",
            status: "not_configured",
            query_terms: [],
            error: "Gazette source adapter is not configured.",
            checked_at: now
          }
        ],
        message: "Gazette source adapters are not configured.",
        checked_at: now,
        disclaimer: "Gazette search is a public-source risk signal, not official ownership verification."
      });
      return;
    }

    const reportMatch = path.match(/^\/cases\/([^/]+)\/report$/);
    if (reportMatch && request.method() === "GET") {
      const report = state.reports[reportMatch[1]] ?? (state.reportAvailable ? reportForCase(state, reportMatch[1]) : null);
      await json(route, report ?? { detail: "Report not found" }, report ? 200 : 404);
      return;
    }

    if (reportMatch && request.method() === "POST") {
      const report = reportForCase(state, reportMatch[1]);
      state.reports[reportMatch[1]] = report;
      state.reportAvailable = true;
      await json(route, report);
      return;
    }

    const pdfMatch = path.match(/^\/cases\/([^/]+)\/report\.pdf$/);
    if (pdfMatch && request.method() === "GET") {
      if (state.gated && !state.paymentSuccessful) {
        await json(
          route,
          { detail: { message: "Payment is required before this paid report can be generated, viewed, or downloaded." } },
          402
        );
        return;
      }
      await route.fulfill({
        status: 200,
        headers: { ...corsHeaders(), "content-type": "application/pdf" },
        body: "%PDF-1.4\n% mocked report"
      });
      return;
    }

    if (path === "/reviews" && request.method() === "POST") {
      const payload = request.postDataJSON() as Partial<ReviewRequest>;
      const role = String(payload.reviewer_role || "advocate");
      const review = makeReview({
        id: `review-${state.reviews.length + 1}`,
        case_id: String(payload.case_id || "case-1"),
        reviewer_role: role,
        reviewer_email: String(payload.reviewer_email || `${role}@example.test`),
        note: String(payload.note || "")
      });
      state.reviews.push(review);
      state.timelineEvents[review.case_id] = [
        ...(state.timelineEvents[review.case_id] ?? []),
        timelineEvent("review_requested", `${reviewRoleTitle(role)} requested`, {
          status: review.status,
          reviewer_role: role
        })
      ];
      await json(route, review);
      return;
    }

    if (path === "/reviews" && request.method() === "GET") {
      await json(route, state.reviews);
      return;
    }

    const assignMatch = path.match(/^\/reviews\/([^/]+)\/assign$/);
    if (assignMatch && request.method() === "POST") {
      const payload = request.postDataJSON() as { assigned_to_user_id?: string };
      const review = state.reviews.find((item) => item.id === assignMatch[1]);
      if (!review) {
        await json(route, { detail: "Review not found" }, 404);
        return;
      }
      review.assigned_to_user_id = payload.assigned_to_user_id ?? null;
      review.status = "assigned";
      await json(route, review);
      return;
    }

    if (path === "/admin/users" && request.method() === "GET") {
      if (state.adminForbidden) {
        await json(route, { detail: "Insufficient role" }, 403);
        return;
      }
      await json(route, [
        {
          id: "admin-1",
          email: "admin@example.test",
          full_name: "Admin User",
          role: "admin",
          created_at: now
        },
        {
          id: "surveyor-1",
          email: "surveyor@example.test",
          full_name: "Surveyor User",
          role: "surveyor",
          created_at: now
        }
      ]);
      return;
    }

    if (path === "/admin/cases" && request.method() === "GET") {
      await json(route, state.cases);
      return;
    }

    if (path === "/payments/mpesa/stk-push" && request.method() === "POST") {
      if (!state.mpesaConfigured) {
        await json(route, {
          status: "not_configured",
          message: "M-Pesa Daraja credentials are not configured.",
          payment: paymentFixture("not_configured")
        });
        return;
      }
      await json(route, {
        status: "initiated",
        message: "M-Pesa STK Push initiated.",
        payment: paymentFixture("initiated")
      });
      return;
    }

    const paymentMatch = path.match(/^\/payments\/([^/]+)$/);
    if (paymentMatch && request.method() === "GET") {
      state.paymentSuccessful = state.paymentPollStatus === "successful";
      await json(route, paymentFixture(state.paymentPollStatus));
      return;
    }

    await json(route, { detail: `Unhandled mock route ${request.method()} ${path}` }, 404);
  });

  return state;
}

export function makeCase(overrides: Partial<ApiCase> = {}): ApiCase {
  return {
    id: "case-1",
    title: "Kitengela parcel purchase",
    buyer_name: "Jane Wanjiku",
    seller_name: "John Mwangi",
    parcel_number_claimed: "LR 209/1234",
    location_county: "Kajiado",
    location: "Kitengela",
    title_number: "IR 556677",
    preferred_language: "en",
    payment_before_verification: false,
    status: "ready_for_analysis",
    risk_level: "medium",
    risk_score: 48,
    created_at: now,
    updated_at: now,
    documents: [],
    ...overrides
  };
}

export function makeDocument(overrides: Partial<ApiDocument> = {}): ApiDocument {
  return {
    id: "doc-1",
    case_id: "case-1",
    category: "title_deed",
    filename: "title-deed.pdf",
    content_type: "application/pdf",
    file_size: 1200,
    sha256: "a".repeat(64),
    status: "clean",
    scan_status: "not_configured",
    image_quality_score: 0.86,
    rejection_reason: "",
    created_at: now,
    detected_document_type: "title_deed",
    document_type_confidence: 0.91,
    extraction_warnings: [],
    extracted_fields: [],
    field_corrections: [],
    ...overrides
  };
}

export function makeReview(overrides: Partial<ReviewRequest> = {}): ReviewRequest {
  return {
    id: "review-1",
    case_id: "case-1",
    assigned_to_user_id: null,
    reviewer_role: "advocate",
    reviewer_email: "advocate@example.test",
    note: "Please review seller authority and consent.",
    status: "requested",
    recommendation: "",
    review_summary: "",
    metadata_json: {},
    created_at: now,
    ...overrides
  };
}

export function pdfFile(name = "title-deed.pdf") {
  return {
    name,
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n% test document")
  };
}

export function pngFile(name = "survey-map.png") {
  return {
    name,
    mimeType: "image/png",
    buffer: Buffer.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52
    ])
  };
}

export async function waitForHydration(page: Page) {
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
}

function reportForCase(state: MockMradiApiState, caseId: string) {
  const landCase = findCase(state, caseId);
  return state.reports[caseId] ?? makeReport({ case_id: caseId, download_url: `/cases/${caseId}/report.pdf` }, landCase);
}

export function makeReport(overrides: Partial<ApiReport>, landCase?: ApiCase): ApiReport;
export function makeReport(overrides?: Partial<ApiReport>): ApiReport;
export function makeReport(overrides: Partial<ApiReport> = {}, landCase?: ApiCase): ApiReport {
  const report = makeReportBase(overrides);
  if (landCase) {
    report.content.case_summary = {
      title: landCase.title,
      county: landCase.location_county,
      parcel_number: landCase.parcel_number_claimed
    };
  }
  return report;
}

function makeReportBase(overrides: Partial<ApiReport> = {}): ApiReport {
  return {
    id: "report-1",
    case_id: "case-1",
    analysis_run_id: "run-1",
    score: 48,
    band: "medium",
    verification_status: "not_verified_from_official_source",
    language: "en",
    created_at: now,
    risk_factors: [
      {
        code: "missing_official_land_search",
        label: "Missing official land search",
        severity: "medium",
        points: 18,
        evidence: { missing_document: "land_search_certificate" },
        recommendation: "Get a fresh official search certificate before paying."
      }
    ],
    report_reference: "MRADI-1",
    download_url: "/cases/case-1/report.pdf",
    is_stale: false,
    stale_reasons: [],
    content: {
      title: "Land Risk Report",
      warning: "AI-assisted, not official verification",
      summary: {
        score: 48,
        band: "medium",
        verification_status: "not verified from official source",
        plain_english: "Medium risk. Confirm official records before payment.",
        kiswahili: "Hatari ya wastani. Hakikisha rekodi rasmi kabla ya malipo."
      },
      missing_documents: [
        {
          code: "missing_land_search_certificate",
          label: "Land search certificate",
          severity: "medium",
          explanation: "A fresh official search certificate was not uploaded."
        }
      ],
      documents_reviewed: [
        {
          category: "title_deed",
          filename: "title-deed.pdf",
          status: "clean",
          confidence_label: "86% confidence"
        }
      ],
      detailed_risk_factors: [
        {
          code: "missing_official_land_search",
          label: "Missing official land search",
          severity: "medium",
          points: 18,
          evidence: { missing_document: "land_search_certificate" },
          recommendation: "Get a fresh official search certificate before paying.",
          trust_evidence: {
            risk_code: "missing_official_land_search",
            risk_label: "Missing official land search",
            what_detected: "No fresh official search certificate was present in the uploaded packet.",
            document_caused: "Upload packet",
            document_id: null,
            extracted_value: "Not uploaded",
            compared_value: "Required document",
            confidence_score: null,
            recommended_action: "Get a fresh official search certificate."
          }
        }
      ],
      trust_evidence_panel: [
        {
          risk_code: "missing_official_land_search",
          risk_label: "Missing official land search",
          what_detected: "No fresh official search certificate was present in the uploaded packet.",
          document_caused: "Upload packet",
          document_id: null,
          extracted_value: "Not uploaded",
          compared_value: "Required document",
          confidence_score: null,
          recommended_action: "Get a fresh official search certificate."
        }
      ],
      human_review_workflow: [
        {
          role: "advocate",
          label: "Advocate review",
          recommended: true,
          reason: "Review sale agreement, seller authority, and missing official search."
        },
        {
          role: "surveyor",
          label: "Surveyor review",
          recommended: false,
          reason: "Confirm parcel boundaries and survey evidence."
        }
      ],
      risk_factors: [
        {
          code: "missing_official_land_search",
          label: "Missing official land search",
          severity: "medium",
          points: 18,
          evidence: { missing_document: "land_search_certificate" },
          recommendation: "Get a fresh official search certificate before paying."
        }
      ],
      recommended_next_steps: ["Get a fresh official search certificate"],
      legal_disclaimer:
        "This report is an AI-assisted risk analysis. It does not replace an official land search, licensed advocate, licensed surveyor, Ardhisasa, Ministry of Lands, or National Land Commission verification."
    },
    ...overrides
  };
}

function findCase(state: MockMradiApiState, caseId: string) {
  return state.cases.find((item) => item.id === caseId);
}

function replaceDocument(state: MockMradiApiState, document: ApiDocument) {
  const landCase = findCase(state, document.case_id);
  if (!landCase) return;
  landCase.documents = landCase.documents.map((item) => (item.id === document.id ? document : item));
}

function timelineEvent(eventType: string, title: string, metadata: Record<string, unknown> = {}): TimelineEvent {
  return {
    id: `${eventType}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    event_type: eventType,
    title,
    metadata_json: metadata,
    created_at: now
  };
}

function paymentFixture(status: string): PaymentRead {
  return {
    id: "payment-1",
    case_id: "case-1",
    provider: "mpesa",
    purpose: "report_unlock",
    amount: "100",
    currency: "KES",
    phone_number: "0712345678",
    status,
    provider_merchant_request_id: "merchant-1",
    provider_checkout_request_id: "checkout-1",
    provider_receipt_number: status === "successful" ? "RCP123" : "",
    result_code: status === "successful" ? "0" : status === "failed" ? "1" : "",
    result_description: status,
    paid_at: status === "successful" ? "2026-05-25T08:01:00" : null,
    created_at: now
  };
}

function reviewRoleTitle(role: string) {
  if (role === "surveyor") return "Surveyor review";
  if (role === "advocate") return "Advocate review";
  return `${role.replaceAll("_", " ")} review`;
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    headers: { ...corsHeaders(), "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "authorization, content-type",
    "access-control-allow-methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS"
  };
}

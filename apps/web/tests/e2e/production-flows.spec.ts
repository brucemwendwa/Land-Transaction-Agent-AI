import { expect, type Page, type Route, test } from "@playwright/test";

const baseCase = {
  id: "case-1",
  title: "Kitengela parcel purchase",
  buyer_name: "Jane Wanjiku",
  seller_name: "John Mwangi",
  parcel_number_claimed: "LR 209/1234",
  location_county: "Kajiado",
  location: "Kitengela",
  title_number: "IR 556677",
  transaction_value: null,
  preferred_language: "en",
  payment_before_verification: false,
  status: "ready_for_analysis",
  risk_level: "medium",
  risk_score: 48,
  created_at: "2026-05-25T08:00:00",
  updated_at: "2026-05-25T08:00:00"
};

function documentFixture(extracted = false) {
  return {
    id: "doc-1",
    case_id: "case-1",
    category: "title_deed",
    filename: "title-deed.pdf",
    content_type: "application/pdf",
    file_size: 1200,
    sha256: "a".repeat(64),
    storage_bucket: "local",
    status: "clean",
    extraction_status: extracted ? "completed" : "pending",
    scan_status: "not_configured",
    image_quality_score: 0.86,
    rejection_reason: "",
    uploaded_at: "2026-05-25T08:00:00",
    created_at: "2026-05-25T08:00:00",
    detected_document_type: "title_deed",
    document_type_confidence: 0.91,
    extraction_warnings: [],
    extracted_fields: extracted
      ? [
          {
            id: "field-1",
            document_id: "doc-1",
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
      : [],
    field_corrections: []
  };
}

const reportFixture = {
  id: "report-1",
  case_id: "case-1",
  analysis_run_id: "run-1",
  score: 48,
  band: "medium",
  verification_status: "not_verified_from_official_source",
  language: "en",
  created_at: "2026-05-25T08:00:00",
  risk_factors: [],
  report_reference: "MRADI-1",
  download_url: "/cases/case-1/report.pdf",
  is_stale: false,
  stale_reasons: [],
  content: {
    title: "Land Risk Report",
    summary: {
      score: 48,
      band: "medium",
      verification_status: "not verified from official source",
      plain_english: "Medium risk. Confirm official records before payment.",
      kiswahili: "Hatari ya wastani. Hakikisha rekodi rasmi kabla ya malipo."
    },
    risk_factors: [],
    recommended_next_steps: ["Get a fresh official search certificate"],
    legal_disclaimer:
      "This report is an AI-assisted risk analysis. It does not replace an official land search, licensed advocate, licensed surveyor, Ardhisasa, Ministry of Lands, or National Land Commission verification."
  }
};

test("sign up and sign in surfaces are available", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
  await page.goto("/sign-up");
  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
});

test("case creation, upload, extraction, analysis, report download, and expert review flow", async ({ page }) => {
  const state = { uploaded: false, extracted: false };
  await mockApi(page, state);

  await page.goto("/cases/new");
  await page.getByLabel("Case title").fill("Kitengela parcel purchase");
  await page.getByLabel("Buyer name").fill("Jane Wanjiku");
  await page.getByLabel("Seller name").fill("John Mwangi");
  await page.getByLabel("Claimed parcel number").fill("LR 209/1234");
  await page.getByLabel("County").fill("Kajiado");
  await page.getByRole("button", { name: /Create and upload documents/ }).click();
  await expect(page).toHaveURL(/\/cases\/case-1\/upload/);

  await page.getByLabel("PDF or image").setInputFiles({
    name: "title-deed.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n% test")
  });
  await page.getByLabel(/I have permission to upload/).check();
  await page.locator("form").last().evaluate((form) => (form as HTMLFormElement).requestSubmit());
  await expect(page.getByText("Document uploaded and queued for extraction.")).toBeVisible();

  await page.getByRole("link", { name: /Review extraction/ }).click();
  await page.getByRole("button", { name: /^Extract$/ }).click();
  await expect(page.getByText("LR 209/1234").first()).toBeVisible();

  await page.getByRole("link", { name: /Analyze/ }).click();
  await page.getByLabel(/I understand this report is AI-assisted/).check();
  await page.getByRole("button", { name: /Run risk analysis/ }).click();
  await expect(page.getByText("Risk report generated and audit events recorded.")).toBeVisible();

  await page.goto("/cases/case-1/download");
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("PDF downloaded.")).toBeVisible();

  await page.goto("/cases/case-1/review");
  await page.getByLabel("Reviewer email").fill("advocate@example.com");
  await page.getByLabel("Note").fill("Please review seller authority and consent.");
  await page.getByRole("button", { name: /Request review/ }).click();
  await expect(page.getByText("Review request saved and audit logged.")).toBeVisible();
});

test("payment-gated report unlock waits for confirmed M-Pesa success", async ({ page }) => {
  const state = { uploaded: true, extracted: true, gated: true, paymentSuccessful: false };
  await mockApi(page, state);

  await page.goto("/cases/case-1/download");
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();
  await page.getByLabel("M-Pesa phone number").fill("0712345678");
  await page.getByRole("button", { name: /Pay KES 100/ }).click();
  await expect(page.getByText("M-Pesa STK Push initiated.")).toBeVisible();
  await page.getByRole("button", { name: /Check status/ }).click();
  await expect(page.getByText("Payment confirmed. You can download the report.")).toBeVisible();
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("PDF downloaded.")).toBeVisible();
});

test("legal and compliance pages expose required disclaimers", async ({ page }) => {
  for (const path of ["/terms", "/privacy", "/data-retention", "/ai-disclaimer"]) {
    await page.goto(path);
    await expect(page.getByText(/This report is an AI-assisted risk analysis/).first()).toBeVisible();
  }
});

test("unauthorized production route protection has a clear configuration-error screen", async ({ page }) => {
  await page.goto("/configuration-error");
  await expect(page.getByRole("heading", { name: /Authentication is not configured/ })).toBeVisible();
});

async function mockApi(page: Page, state: { uploaded?: boolean; extracted?: boolean; gated?: boolean; paymentSuccessful?: boolean }) {
  await page.route("http://127.0.0.1:3002/mock-upload/**", async (route) => {
    state.uploaded = true;
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
      state.uploaded = true;
      await route.fulfill({ status: 200, headers: corsHeaders(), body: "" });
      return;
    }

    if (path === "/cases" && request.method() === "POST") {
      await json(route, { ...baseCase, documents: [] });
      return;
    }

    if (path === "/cases/case-1" && request.method() === "GET") {
      await json(route, { ...baseCase, documents: state.uploaded ? [documentFixture(Boolean(state.extracted))] : [] });
      return;
    }

    if (path === "/uploads/signed-url" && request.method() === "POST") {
      await json(route, {
        document_id: "doc-1",
        upload_url: "http://127.0.0.1:3002/mock-upload/doc-1",
        method: "PUT",
        headers: { "content-type": "application/pdf" },
        expires_at: "2026-05-25T08:15:00"
      });
      return;
    }

    if (path === "/uploads/complete" && request.method() === "POST") {
      state.uploaded = true;
      await json(route, { document_id: "doc-1", status: "clean", scan_status: "not_configured" });
      return;
    }

    if (path === "/documents/doc-1/extract" && request.method() === "POST") {
      state.extracted = true;
      await json(route, { document: documentFixture(true), extracted_fields: documentFixture(true).extracted_fields, verification_status: "not_checked" });
      return;
    }

    if (path === "/cases/case-1/analysis" && request.method() === "POST") {
      await json(route, reportFixture);
      return;
    }

    if (path === "/cases/case-1/report.pdf" && request.method() === "GET") {
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
        body: "%PDF-1.4\n% mocked"
      });
      return;
    }

    if (path === "/reviews" && request.method() === "POST") {
      await json(route, {
        id: "review-1",
        case_id: "case-1",
        assigned_to_user_id: null,
        reviewer_role: "advocate",
        reviewer_email: "advocate@example.com",
        note: "Please review seller authority and consent.",
        status: "requested",
        recommendation: "",
        review_summary: "",
        metadata_json: {},
        created_at: "2026-05-25T08:00:00"
      });
      return;
    }

    if (path === "/payments/mpesa/stk-push" && request.method() === "POST") {
      await json(route, {
        status: "initiated",
        message: "M-Pesa STK Push initiated.",
        payment: paymentFixture("initiated")
      });
      return;
    }

    if (path === "/payments/payment-1" && request.method() === "GET") {
      state.paymentSuccessful = true;
      await json(route, paymentFixture("successful"));
      return;
    }

    await json(route, { detail: `Unhandled mock route ${request.method()} ${path}` }, 404);
  });
}

function paymentFixture(status: string) {
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
    result_code: status === "successful" ? "0" : "",
    result_description: status,
    paid_at: status === "successful" ? "2026-05-25T08:01:00" : null,
    created_at: "2026-05-25T08:00:00"
  };
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
    "access-control-allow-origin": "http://127.0.0.1:3002",
    "access-control-allow-headers": "authorization, content-type",
    "access-control-allow-methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS"
  };
}

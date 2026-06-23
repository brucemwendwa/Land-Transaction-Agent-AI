import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, waitForHydration } from "./support/mradi-api";

test("payment page loads", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()], reportAvailable: true });

  await page.goto("/cases/case-1/download", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: "Download report" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Download PDF/ })).toBeVisible();
});

test("missing M-Pesa config shows a clear error", async ({ page }) => {
  await mockMradiApi(page, {
    cases: [makeCase()],
    gated: true,
    mpesaConfigured: false,
    reportAvailable: true
  });

  await page.goto("/cases/case-1/download", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();
  await page.getByLabel("M-Pesa phone number").fill("0712345678");
  await page.getByRole("button", { name: /Pay KES 100/ }).click();

  await expect(page.getByText("M-Pesa Daraja credentials are not configured.")).toBeVisible();
  await expect(page.getByText("Status: not configured")).toBeVisible();
});

test("configured payment request creates a pending state", async ({ page }) => {
  await mockMradiApi(page, {
    cases: [makeCase()],
    gated: true,
    paymentPollStatus: "pending",
    reportAvailable: true
  });

  await page.goto("/cases/case-1/download", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();
  await page.getByLabel("M-Pesa phone number").fill("0712345678");
  await page.getByRole("button", { name: /Pay KES 100/ }).click();

  await expect(page.getByText("M-Pesa STK Push initiated.")).toBeVisible();
  await expect(page.getByText("Status: initiated")).toBeVisible();
});

test("failed payment does not unlock report", async ({ page }) => {
  await mockMradiApi(page, {
    cases: [makeCase()],
    gated: true,
    paymentPollStatus: "failed",
    reportAvailable: true
  });

  await page.goto("/cases/case-1/download", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();

  await page.getByLabel("M-Pesa phone number").fill("0712345678");
  await page.getByRole("button", { name: /Pay KES 100/ }).click();
  await page.getByRole("button", { name: /Check status/ }).click();
  await expect(page.getByText("Payment status: failed")).toBeVisible();

  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();
});

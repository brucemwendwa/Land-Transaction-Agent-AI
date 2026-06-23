import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, waitForHydration } from "./support/mradi-api";

test("report preview loads with disclaimer and PDF download control", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()], reportAvailable: true });

  await page.goto("/cases/case-1/report", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByRole("heading", { name: "Land Risk Report" })).toBeVisible();
  await expect(page.getByRole("main").getByText(/This report is an AI-assisted risk analysis/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Download PDF/ })).toBeVisible();
});

test("paid report remains locked until payment succeeds", async ({ page }) => {
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
  await expect(page.getByText("Status: initiated")).toBeVisible();
  await page.getByRole("button", { name: /Check status/ }).click();
  await expect(page.getByText("Payment status: failed")).toBeVisible();

  await page.getByRole("button", { name: /Download PDF/ }).click();
  await expect(page.getByText("Payment is required before this report can be downloaded.")).toBeVisible();
});

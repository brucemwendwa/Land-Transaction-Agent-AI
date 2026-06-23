import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, waitForHydration } from "./support/mradi-api";

test("risk analysis page loads", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()] });

  await page.goto("/cases/case-1/analysis", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: "Case analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Run risk analysis/ })).toBeVisible();
});

test("risk analysis page warns when required documents are missing", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase({ documents: [] })] });

  await page.goto("/cases/case-1/analysis", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByRole("heading", { name: "Missing documents" })).toBeVisible();
  await expect(page.getByText("title deed")).toBeVisible();
  await expect(page.getByText("land search certificate")).toBeVisible();
});

test("risk score and evidence panel appear after analysis", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()] });

  await page.goto("/cases/case-1/analysis", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await page.getByLabel(/I understand this report is AI-assisted/).check();
  await page.getByRole("button", { name: /Run risk analysis/ }).click();

  await expect(page.getByText("Risk report generated and audit events recorded.")).toBeVisible();
  await expect(page.getByText("48").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence panel" })).toBeVisible();
  await expect(page.getByText("Missing official land search").first()).toBeVisible();
});

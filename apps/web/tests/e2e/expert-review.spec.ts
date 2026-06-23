import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, waitForHydration } from "./support/mradi-api";

test("user can request advocate review and see review status in timeline", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()] });

  await page.goto("/cases/case-1/review?role=advocate", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await expect(page.getByLabel("Reviewer type")).toHaveValue("advocate");
  await page.getByLabel("Reviewer email").fill("advocate@example.test");
  await page.getByLabel("Note").fill("Please review seller authority and consent.");
  await page.getByRole("button", { name: /Request review/ }).click();
  await expect(page.getByText("Review request saved and audit logged.")).toBeVisible();

  await page.goto("/cases/case-1/timeline", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await expect(page.getByText("Advocate review requested")).toBeVisible();
  await expect(page.getByRole("main").getByText("status: requested")).toBeVisible();
});

test("user can request surveyor review", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()] });

  await page.goto("/cases/case-1/review?role=surveyor", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await expect(page.getByLabel("Reviewer type")).toHaveValue("surveyor");
  await page.getByLabel("Reviewer email").fill("surveyor@example.test");
  await page.getByLabel("Note").fill("Please review boundary and survey evidence.");
  await page.getByRole("button", { name: /Request review/ }).click();

  await expect(page.getByText("Review request saved and audit logged.")).toBeVisible();
});

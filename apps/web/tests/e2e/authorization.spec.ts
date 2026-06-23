import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, waitForHydration } from "./support/mradi-api";

test("User A cannot access User B case", async ({ page }) => {
  await mockMradiApi(page, {
    cases: [makeCase()],
    inaccessibleCaseIds: ["other-user-case"]
  });

  await page.goto("/cases/other-user-case/upload", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByText("Case is not accessible").first()).toBeVisible();
});

test("non-admin cannot access admin dashboard data", async ({ page }) => {
  await mockMradiApi(page, {
    adminForbidden: true,
    cases: [makeCase()]
  });

  await page.goto("/admin", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  await expect(page.getByText("Insufficient role")).toBeVisible();
});

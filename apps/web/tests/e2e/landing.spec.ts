import { expect, test } from "@playwright/test";

test("landing page explains the core product", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
  await expect(page.getByText("Trust and safety disclaimer")).toBeVisible();
});

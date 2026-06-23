import { expect, test } from "@playwright/test";
import { mockMradiApi, waitForHydration } from "./support/mradi-api";

test("new case form validates required fields", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/cases/new", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /Create and upload documents/ }).click();

  await expect(page).toHaveURL(/\/cases\/new$/);
  await expect(page.locator("#title")).toBeFocused();
  await expect
    .poll(() => page.locator("#title").evaluate((input: HTMLInputElement) => input.validity.valueMissing))
    .toBe(true);
});

test("user can create a new land case and see it in the dashboard", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/cases/new", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  await page.getByLabel("Case title").fill("E2E test parcel purchase");
  await page.getByLabel("Buyer name").fill("Test Buyer");
  await page.getByLabel("Seller name").fill("Test Seller");
  await page.getByLabel("Claimed parcel number").fill("LR E2E/001");
  await page.getByLabel("County").fill("Nairobi");

  await Promise.all([
    page.waitForURL(/\/cases\/case-1\/upload/, { waitUntil: "domcontentloaded" }),
    page.getByRole("button", { name: /Create and upload documents/ }).click()
  ]);
  await expect(page.getByRole("heading", { name: "E2E test parcel purchase" })).toBeVisible();

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByRole("heading", { name: "E2E test parcel purchase" })).toBeVisible();
});

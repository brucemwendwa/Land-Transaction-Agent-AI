import { expect, test } from "@playwright/test";
import { mockMradiApi } from "./support/mradi-api";

test("landing page has no browser console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test("landing page explains the core product", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
  await expect(page.getByText("No ownership overclaims")).toBeVisible();
  await expect(page.getByText(/AI assistance, not legal advice/)).toBeVisible();
});

test("landing page navigation links move to the expected sections", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "The landing anchor navigation is hidden in the compact mobile header.");

  await page.goto("/", { waitUntil: "domcontentloaded" });
  const navigation = page.getByRole("navigation", { name: "Landing navigation" });

  await navigation.getByRole("link", { name: "Fraud problem" }).click();
  await expect(page).toHaveURL(/#problem$/);
  await expect(page.locator("#problem")).toBeInViewport();

  await navigation.getByRole("link", { name: "How it works" }).click();
  await expect(page).toHaveURL(/#how$/);
  await expect(page.locator("#how")).toBeInViewport();

  await navigation.getByRole("link", { name: "Report preview" }).click();
  await expect(page).toHaveURL(/#report$/);
  await expect(page.locator("#report")).toBeInViewport();

  await navigation.getByRole("link", { name: "FAQ" }).click();
  await expect(page).toHaveURL(/#faq$/);
  await expect(page.locator("#faq")).toBeInViewport();
});

test("landing page login button opens sign in", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("link", { name: "Login" }).click();

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
});

test("landing page dashboard button redirects to dashboard", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("link", { name: "Dashboard" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Land transaction cases" })).toBeVisible();
});

import { expect, test } from "@playwright/test";

test("sign-in page loads without email OTP in local E2E", async ({ page }) => {
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue to dashboard" })).toHaveAttribute("href", "/dashboard");
});

test("sign-up page loads without email OTP in local E2E", async ({ page }) => {
  await page.goto("/sign-up", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue to dashboard" })).toHaveAttribute("href", "/dashboard");
});

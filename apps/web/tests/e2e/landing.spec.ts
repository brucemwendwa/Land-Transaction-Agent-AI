import { expect, test } from "@playwright/test";

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

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test("landing page explains the core product", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
  await expect(page.getByText("No ownership overclaims")).toBeVisible();
  await expect(page.getByText(/AI assistance, not legal advice/)).toBeVisible();
});

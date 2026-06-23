import { expect, test } from "@playwright/test";

test("logged-out users cannot access dashboard", async ({ context, page }) => {
  await context.addCookies([
    {
      name: "mradi_e2e_signed_out",
      value: "true",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax"
    }
  ]);

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: /Development authentication is enabled/ })).toBeVisible();
});

test("missing Clerk keys show a clear configuration error", async ({ page }) => {
  await page.goto("/configuration-error", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Authentication is not configured/ })).toBeVisible();
  await expect(page.getByText("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", { exact: true })).toBeVisible();
  await expect(page.getByText("CLERK_SECRET_KEY", { exact: true })).toBeVisible();
  await expect(page.getByText(/Production sign-in requires a real Clerk publishable key and secret key/)).toBeVisible();
});

test("content security policy allows Clerk CAPTCHA resources", async ({ page }) => {
  const response = await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  const csp = response?.headers()["content-security-policy"] ?? "";

  expect(csp).toContain("script-src");
  expect(csp).toContain("frame-src");
  expect(csp).toContain("worker-src 'self' blob:");
  expect(csp).toContain("https://challenges.cloudflare.com");
});

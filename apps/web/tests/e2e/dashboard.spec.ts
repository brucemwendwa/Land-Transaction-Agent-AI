import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi } from "./support/mradi-api";

test("authenticated test user can access dashboard", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase()] });

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: "Land transaction cases" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Kitengela parcel purchase" })).toBeVisible();
  await expect(page.getByText("Total cases")).toBeVisible();
});

test("dashboard empty state appears when no cases exist", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: "Start with a transaction case" })).toBeVisible();
  await expect(page.getByText("Create a case, upload documents, and generate a risk report")).toBeVisible();
});

test("dashboard create case button opens the new case form", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await page.getByRole("main").getByRole("link", { name: /New case/ }).click();

  await expect(page).toHaveURL(/\/cases\/new$/);
  await expect(page.getByRole("heading", { name: "Create case" })).toBeVisible();
});

test("dashboard navigation can return to the public homepage", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Home" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: /Before You Buy Land/ })).toBeVisible();
});

test("primary navigation keeps every app route visible on small screens", async ({ page }) => {
  await mockMradiApi(page, { cases: [] });

  await page.goto("/reviews", { waitUntil: "domcontentloaded" });

  const navigation = page.getByRole("navigation", { name: "Primary navigation" });
  for (const label of ["Home", "Dashboard", "New case", "Reviews", "Expert", "Admin", "Audit", "Settings"]) {
    await expect(navigation.getByRole("link", { name: label })).toBeVisible();
  }

  await expect
    .poll(async () =>
      navigation.evaluate((element) => {
        const navBounds = element.getBoundingClientRect();
        const linkBounds = Array.from(element.querySelectorAll("a")).map((link) => link.getBoundingClientRect());

        return linkBounds.every((bounds) => bounds.left >= navBounds.left - 1 && bounds.right <= navBounds.right + 1);
      })
    )
    .toBe(true);
});

import { expect, test } from "@playwright/test";
import { makeCase, mockMradiApi, pdfFile, pngFile, waitForHydration } from "./support/mradi-api";

test("upload page loads for an existing case", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase({ documents: [] })] });

  await page.goto("/cases/case-1/upload", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);

  await expect(page.getByRole("heading", { name: "Kitengela parcel purchase" })).toBeVisible();
  await expect(page.getByText("Upload document")).toBeVisible();
  await expect(page.getByLabel("PDF or image")).toBeAttached();
});

test("unsupported upload file type is rejected", async ({ page }) => {
  await mockMradiApi(page, { cases: [makeCase({ documents: [] })] });

  await page.goto("/cases/case-1/upload", { waitUntil: "domcontentloaded" });
  await waitForHydration(page);
  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["not a supported document"], "notes.txt", { type: "text/plain" }));
    return transfer;
  });
  await page.getByText("Drop files here or browse").dispatchEvent("drop", { dataTransfer });

  await expect(page.locator("form").getByText("Upload PDF, PNG, JPG, JPEG, or WEBP files only.")).toBeVisible();
});

for (const fixture of [
  { label: "PDF", file: pdfFile("title-deed.pdf") },
  { label: "image", file: pngFile("survey-map.png") }
]) {
  test(`valid ${fixture.label} upload is accepted and shows upload status`, async ({ page }) => {
    await mockMradiApi(page, { cases: [makeCase({ documents: [] })] });

    await page.goto("/cases/case-1/upload", { waitUntil: "domcontentloaded" });
    await waitForHydration(page);
    await page.getByLabel("PDF or image").setInputFiles(fixture.file);
    await page.getByLabel(/I have permission to upload/).check();
    const uploadButton = page.getByRole("button", { name: /Upload securely/ });
    await expect(uploadButton).toBeEnabled();
    await uploadButton.click();

    await expect(page.getByText("Upload complete")).toBeVisible();
    await expect(page.getByText("Document uploaded and queued for extraction.")).toBeVisible();
    await expect(page.getByText(fixture.file.name)).toBeVisible();
  });
}

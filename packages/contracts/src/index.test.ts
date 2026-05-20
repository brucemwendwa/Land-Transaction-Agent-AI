import { describe, expect, it } from "vitest";
import { documentCategories } from "./index";

describe("shared land transaction contracts", () => {
  it("keeps the core due-diligence document categories stable and unique", () => {
    const required = [
      "title_deed",
      "sale_agreement",
      "national_id_or_passport",
      "kra_pin_certificate",
      "land_search_certificate",
      "consent_to_transfer",
      "rates_clearance_certificate",
      "land_rent_clearance_certificate"
    ];

    expect(new Set(documentCategories).size).toBe(documentCategories.length);
    expect(documentCategories).toEqual(expect.arrayContaining(required));
  });
});

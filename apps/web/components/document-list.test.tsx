import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApiDocument } from "@/lib/api";
import { DocumentList, MissingDocumentsWarning } from "@/components/document-list";

const requiredCategories = [
  "title_deed",
  "sale_agreement",
  "national_id_or_passport",
  "kra_pin_certificate",
  "land_search_certificate",
  "consent_to_transfer",
  "rates_clearance_certificate",
  "land_rent_clearance_certificate"
] as const;

function documentFixture(overrides: Partial<ApiDocument> = {}): ApiDocument {
  return {
    id: "doc-1",
    case_id: "case-1",
    category: "title_deed",
    filename: "title.pdf",
    content_type: "application/pdf",
    file_size: 1024,
    sha256: "a".repeat(64),
    status: "extracted",
    scan_status: "clean",
    image_quality_score: 0.92,
    rejection_reason: "",
    created_at: "2026-05-20T08:00:00Z",
    extracted_fields: [],
    field_corrections: [],
    detected_document_type: "title_deed",
    document_type_confidence: 0.91,
    extraction_warnings: [],
    ...overrides
  };
}

describe("DocumentList", () => {
  it("shows a useful empty state before uploads", () => {
    render(<DocumentList documents={[]} />);

    expect(screen.getByText("No documents uploaded yet")).toBeInTheDocument();
    expect(screen.getByText(/fresh land search certificate/i)).toBeInTheDocument();
  });

  it("surfaces rejected uploads and extraction warnings", () => {
    render(
      <DocumentList
        documents={[
          documentFixture({
            status: "rejected",
            image_quality_score: 0.31,
            extraction_warnings: [{ code: "poor_image_quality", severity: "medium", message: "Scan is too blurry." }]
          })
        ]}
      />
    );

    expect(screen.getByText("title.pdf")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
    expect(screen.getByText("31% confidence")).toBeInTheDocument();
    expect(screen.getByText("Scan is too blurry.")).toBeInTheDocument();
  });
});

describe("MissingDocumentsWarning", () => {
  it("lists required documents still absent from the due-diligence packet", () => {
    render(
      <MissingDocumentsWarning
        documents={[
          documentFixture({ id: "title", category: "title_deed" }),
          documentFixture({ id: "sale", category: "sale_agreement", filename: "sale.pdf" })
        ]}
      />
    );

    expect(screen.getByText("Missing documents")).toBeInTheDocument();
    expect(screen.getByText("land search certificate")).toBeInTheDocument();
    expect(screen.getByText("consent to transfer")).toBeInTheDocument();
  });

  it("confirms when every core document category is present", () => {
    render(
      <MissingDocumentsWarning
        documents={requiredCategories.map((category) =>
          documentFixture({ id: category, category, filename: `${category}.pdf` })
        )}
      />
    );

    expect(screen.getByText("Core document set uploaded")).toBeInTheDocument();
    expect(screen.queryByText("Missing documents")).not.toBeInTheDocument();
  });
});

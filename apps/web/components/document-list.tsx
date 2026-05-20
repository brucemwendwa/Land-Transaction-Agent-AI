import { AlertTriangle, FileCheck2, FileWarning, ShieldCheck } from "lucide-react";
import type { DocumentCategory } from "@mradi/contracts";
import type { ApiDocument } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/state-views";

const requiredCategories: DocumentCategory[] = [
  "title_deed",
  "sale_agreement",
  "national_id_or_passport",
  "kra_pin_certificate",
  "land_search_certificate",
  "consent_to_transfer",
  "rates_clearance_certificate",
  "land_rent_clearance_certificate"
];

export function DocumentList({ documents }: { documents: ApiDocument[] }) {
  if (!documents.length) {
    return (
      <EmptyState
        title="No documents uploaded yet"
        description="Start with the title deed, sale agreement, ID or passport, KRA PIN, and a fresh land search certificate."
      />
    );
  }
  return (
    <div className="space-y-3">
      {documents.map((document) => (
        <Card key={document.id} className="premium-panel">
          <CardContent className="grid gap-4 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
            <div className="flex min-w-0 items-center gap-3">
              {document.status === "rejected" ? (
                <FileWarning className="h-5 w-5 shrink-0 text-red-600" aria-hidden="true" />
              ) : (
                <FileCheck2 className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              )}
              <div className="min-w-0">
                <div className="truncate font-medium">{document.filename}</div>
                <div className="text-xs text-muted-foreground">{document.category.replaceAll("_", " ")}</div>
                {document.extraction_warnings.length ? (
                  <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-300">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    <span>{document.extraction_warnings[0].message}</span>
                  </div>
                ) : null}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              <StatusBadge tone={statusToneFromValue(document.status)} label={document.status.replaceAll("_", " ")} />
              <StatusBadge
                tone={document.image_quality_score === null ? "neutral" : document.image_quality_score < 0.45 ? "needs_review" : "verified"}
                label={document.image_quality_score === null ? "Confidence pending" : `${Math.round(document.image_quality_score * 100)}% confidence`}
              />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function MissingDocumentsWarning({ documents }: { documents: ApiDocument[] }) {
  const uploaded = new Set(documents.map((document) => document.category));
  const missing = requiredCategories.filter((category) => !uploaded.has(category));
  if (!missing.length) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/10">
        <CardContent className="flex items-start gap-3 p-4 text-sm">
          <ShieldCheck className="mt-0.5 h-5 w-5 text-emerald-700 dark:text-emerald-300" aria-hidden="true" />
          <div>
            <div className="font-medium">Core document set uploaded</div>
            <p className="mt-1 text-muted-foreground">You can still add supporting documents before analysis.</p>
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-amber-500/30 bg-amber-500/10">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-5 w-5 text-amber-700 dark:text-amber-300" aria-hidden="true" />
          Missing documents
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          These are commonly needed before a buyer relies on a land transaction report.
        </p>
        <div className="flex flex-wrap gap-2">
          {missing.map((category) => (
            <span key={category} className="rounded-md border bg-background px-2.5 py-1 text-xs font-medium">
              {category.replaceAll("_", " ")}
            </span>
          ))}
        </div>
        <Progress value={Math.round(((requiredCategories.length - missing.length) / requiredCategories.length) * 100)} />
      </CardContent>
    </Card>
  );
}

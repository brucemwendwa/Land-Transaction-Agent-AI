"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { AlertTriangle, ArrowRight, ExternalLink, Save, ScanLine, ScanText, ShieldQuestion } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { ProgressTracker } from "@/components/progress-tracker";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { EmptyState, ErrorState, LoadingPanel, SuccessState } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, type ApiCase, type ApiDocument } from "@/lib/api";

export default function ExtractionPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAuth();
  const [landCase, setLandCase] = useState<ApiCase | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [savingCorrectionId, setSavingCorrectionId] = useState<string | null>(null);
  const [corrections, setCorrections] = useState<Record<string, { value: string; reason: string }>>({});

  const load = useCallback(async () => {
    const token = await getToken();
    setLandCase(await apiFetch<ApiCase>(`/cases/${params.caseId}`, token));
  }, [getToken, params.caseId]);

  useEffect(() => {
    void (async () => {
      try {
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load case");
      } finally {
        setLoading(false);
      }
    })();
  }, [load]);

  async function extract(document: ApiDocument) {
    setStatus(`Extracting ${document.filename}...`);
    setError("");
    setExtractingId(document.id);
    try {
      const token = await getToken();
      await apiFetch(`/documents/${document.id}/extract`, token, { method: "POST" });
      await load();
      setStatus("Extraction complete");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setExtractingId(null);
    }
  }

  async function openDocument(document: ApiDocument) {
    setError("");
    try {
      const token = await getToken();
      const response = await apiFetch<{ read_url: string }>(`/documents/${document.id}/read-url`, token);
      window.open(response.read_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open source document");
    }
  }

  async function saveCorrection(document: ApiDocument, field: ApiDocument["extracted_fields"][number]) {
    const correction = corrections[field.id];
    if (!correction?.value.trim()) {
      setError("Enter a corrected value before saving.");
      return;
    }
    setSavingCorrectionId(field.id);
    setError("");
    try {
      const token = await getToken();
      await apiFetch(`/documents/${document.id}/corrections`, token, {
        method: "POST",
        body: JSON.stringify({
          extracted_field_id: field.id,
          field_name: field.field_name,
          corrected_value: correction.value,
          reason: correction.reason
        })
      });
      setCorrections((current) => ({ ...current, [field.id]: { value: "", reason: "" } }));
      await load();
      setStatus("Correction saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save correction");
    } finally {
      setSavingCorrectionId(null);
    }
  }

  async function extractAll() {
    if (!landCase) return;
    for (const document of landCase.documents.filter((item) => ["clean", "needs_review"].includes(item.status))) {
      await extract(document);
    }
  }

  const documents = landCase?.documents ?? [];
  const extractedCount = documents.filter((document) => document.extracted_fields.length > 0).length;
  const progress = documents.length ? Math.round((extractedCount / documents.length) * 100) : 0;

  return (
    <AppShell>
      <ProgressTracker current="extraction" />
      <div className="mt-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Document intelligence</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Extraction review</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Review the extracted parcel, owner, ID, date, registry, section, block, and plot signals before running the risk engine.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="outline" onClick={extractAll} disabled={!documents.length || extractingId !== null}>
            <ScanText className="h-4 w-4" /> Extract all
          </Button>
          <Button asChild><Link href={`/cases/${params.caseId}/analysis`}>Analyze <ArrowRight className="h-4 w-4" /></Link></Button>
        </div>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading extraction workspace" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} onRetry={() => void load()} /></div> : null}
      {status === "Extraction complete" ? <SuccessState className="mt-6" message="Extraction saved. Review confidence before analysis." /> : null}
      {status === "Correction saved" ? <SuccessState className="mt-6" message="Correction saved separately from AI extraction." /> : null}

      {!loading && !error && !documents.length ? (
        <div className="mt-6">
          <EmptyState
            title="Upload documents before extraction"
            description="At least one clean or reviewable document is required before the extraction agent can read transaction fields."
            action={<Button asChild><Link href={`/cases/${params.caseId}/upload`}>Upload documents</Link></Button>}
          />
        </div>
      ) : null}

      {documents.length ? (
        <div className="mt-6 space-y-4">
          <Card className="premium-panel">
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-medium">{extractedCount} of {documents.length} documents have extracted fields</span>
                <span className="text-muted-foreground">{progress}% reviewed</span>
              </div>
              <Progress value={progress} />
            </CardContent>
          </Card>

          <div className="grid gap-4">
            {documents.map((document, index) => (
              <motion.article
                key={document.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.035 }}
              >
                <Card className="premium-panel">
                  <CardHeader>
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                      <div className="min-w-0">
                        <CardTitle className="truncate">{document.filename}</CardTitle>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {document.category.replaceAll("_", " ")}
                          {document.detected_document_type ? ` · detected ${document.detected_document_type.replaceAll("_", " ")}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <StatusBadge tone={statusToneFromValue(document.status)} label={document.status.replaceAll("_", " ")} />
                        <StatusBadge tone={confidenceTone(document.image_quality_score)} label={confidenceLabel(document.image_quality_score)} />
                        <Button variant="outline" size="sm" onClick={() => void openDocument(document)}>
                          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                          Source
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {document.extraction_warnings.length ? (
                      <div className="mb-4 space-y-2">
                        {document.extraction_warnings.map((warning) => (
                          <div key={`${document.id}-${warning.code}`} className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                            <div>
                              <div className="font-medium">{warning.code.replaceAll("_", " ")}</div>
                              <p className="mt-1 leading-6">{warning.message}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {document.extracted_fields.length ? (
                      <div className="grid gap-3 md:grid-cols-2">
                        {document.extracted_fields.map((field) => (
                          <div key={field.id} className="rounded-lg border bg-background/70 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{field.field_name.replaceAll("_", " ")}</div>
                              <span className="text-xs text-muted-foreground">{Math.round(field.confidence * 100)}%</span>
                            </div>
                            <div className="mt-2 break-words font-medium">{field.value || "Not recorded"}</div>
                            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                              <ShieldQuestion className="h-3.5 w-3.5" aria-hidden="true" />
                              {field.source}{field.page_number ? ` · page ${field.page_number}` : ""}
                            </div>
                            {field.text_snippet ? (
                              <blockquote className="mt-3 rounded-md border-l-2 border-primary/60 bg-muted/40 px-3 py-2 text-xs leading-5 text-muted-foreground">
                                {field.text_snippet}
                              </blockquote>
                            ) : null}
                            <div className="mt-3 space-y-2 rounded-md border bg-muted/30 p-3">
                              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reviewer correction</div>
                              <Input
                                aria-label={`Correct ${field.field_name}`}
                                value={corrections[field.id]?.value ?? ""}
                                placeholder="Enter corrected value"
                                onChange={(event) =>
                                  setCorrections((current) => ({
                                    ...current,
                                    [field.id]: { value: event.target.value, reason: current[field.id]?.reason ?? "" }
                                  }))
                                }
                              />
                              <Textarea
                                aria-label={`Reason for correcting ${field.field_name}`}
                                value={corrections[field.id]?.reason ?? ""}
                                placeholder="Reason or source, for example confirmed against uploaded search certificate"
                                rows={2}
                                onChange={(event) =>
                                  setCorrections((current) => ({
                                    ...current,
                                    [field.id]: { value: current[field.id]?.value ?? "", reason: event.target.value }
                                  }))
                                }
                              />
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => void saveCorrection(document, field)}
                                disabled={savingCorrectionId === field.id}
                              >
                                <Save className="h-3.5 w-3.5" aria-hidden="true" />
                                {savingCorrectionId === field.id ? "Saving..." : "Save correction"}
                              </Button>
                              {document.field_corrections.filter((item) => item.field_name === field.field_name).length ? (
                                <div className="space-y-1 border-t pt-2 text-xs text-muted-foreground">
                                  {document.field_corrections
                                    .filter((item) => item.field_name === field.field_name)
                                    .slice(0, 2)
                                    .map((item) => (
                                      <div key={item.id}>
                                        Saved correction: <span className="font-medium text-foreground">{item.corrected_value}</span>
                                      </div>
                                    ))}
                                </div>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col justify-between gap-3 rounded-lg border bg-muted/40 p-4 sm:flex-row sm:items-center">
                        <div className="flex gap-3">
                          <ScanLine className="mt-0.5 h-5 w-5 text-primary" aria-hidden="true" />
                          <div>
                            <div className="font-medium">No fields extracted yet</div>
                            <p className="mt-1 text-sm text-muted-foreground">Run extraction to populate parcel, party, and date signals.</p>
                          </div>
                        </div>
                        <Button variant="outline" onClick={() => extract(document)} disabled={extractingId !== null}>
                          {extractingId === document.id ? "Extracting..." : "Extract"}
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.article>
            ))}
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function confidenceTone(score: number | null) {
  if (score === null) return "neutral" as const;
  if (score < 0.45) return "needs_review" as const;
  if (score < 0.7) return "not_verified" as const;
  return "verified" as const;
}

function confidenceLabel(score: number | null) {
  return score === null ? "Confidence pending" : `${Math.round(score * 100)}% confidence`;
}

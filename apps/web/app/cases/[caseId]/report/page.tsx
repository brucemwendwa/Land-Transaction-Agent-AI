"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import {
  AlertTriangle,
  Download,
  FileText,
  FileWarning,
  Languages,
  Landmark,
  RefreshCw,
  Scale,
  Search,
  Share2,
  ShieldCheck,
  TableProperties,
  UserRoundCheck
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { ProgressTracker } from "@/components/progress-tracker";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingPanel, SuccessState } from "@/components/state-views";
import { apiFetch, apiUrl, type ApiReport, type ApiRiskFactor } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

type ReportRecord = Record<string, unknown>;

export default function ReportPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAppAuth();
  const [report, setReport] = useState<ApiReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<"idle" | "generating" | "downloading">("idle");
  const [acceptedDisclaimer, setAcceptedDisclaimer] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  async function loadReport() {
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      setReport(await apiFetch<ApiReport>(`/cases/${params.caseId}/report`, token));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load report";
      if (message.includes("Report not found") || message.includes("404")) {
        setReport(null);
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.caseId]);

  async function generateReport(forceRegenerate: boolean) {
    setWorking("generating");
    setError("");
    setDownloaded(false);
    try {
      const token = await getToken();
      const nextReport = await apiFetch<ApiReport>(`/cases/${params.caseId}/report`, token, {
        method: "POST",
        body: JSON.stringify({
          accepted_legal_disclaimer: acceptedDisclaimer,
          force_regenerate: forceRegenerate
        })
      });
      setReport(nextReport);
      setAcceptedDisclaimer(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate report");
    } finally {
      setWorking("idle");
    }
  }

  async function downloadReport() {
    setWorking("downloading");
    setError("");
    setDownloaded(false);
    try {
      const token = await getToken();
      const response = await fetch(apiUrl(`/cases/${params.caseId}/report.pdf`), {
        headers: token ? { authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Unable to download PDF");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mradi-wa-ardhi-${report?.report_reference ?? params.caseId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setDownloaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to download report");
    } finally {
      setWorking("idle");
    }
  }

  const content = report?.content;
  const riskFactors = useMemo(
    () => content?.detailed_risk_factors ?? content?.risk_factors ?? [],
    [content]
  );

  return (
    <AppShell>
      <ProgressTracker current="report" />

      {loading ? <div className="mt-6"><LoadingPanel label="Loading risk report" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={humanError(error)} /></div> : null}

      {!loading && !error && !report ? (
        <div className="mt-6">
          <EmptyState
            title="No report available yet"
            description="Generate a downloadable buyer-facing risk report after uploading and reviewing the case documents."
            action={
              <GenerateControls
                accepted={acceptedDisclaimer}
                disabled={working === "generating"}
                label={working === "generating" ? "Generating..." : "Generate report"}
                onAcceptedChange={setAcceptedDisclaimer}
                onGenerate={() => generateReport(true)}
              />
            }
          />
        </div>
      ) : null}

      {report && content ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28 }}
            className="space-y-5"
          >
            <section className="rounded-lg border bg-card p-6 shadow-sm">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                <div>
                  <p className="text-sm font-semibold text-primary">{content.brand ?? "Mradi wa Ardhi"}</p>
                  <h1 className="mt-2 text-3xl font-semibold tracking-tight">{content.title}</h1>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <StatusBadge tone={statusToneFromValue(report.verification_status)} label={report.verification_status.replaceAll("_", " ")} />
                    <Badge variant="outline">Report ID {report.report_reference || content.report_id || report.id}</Badge>
                    <Badge variant="outline">Generated {formatDate(content.generated_at ?? report.created_at)}</Badge>
                  </div>
                </div>
                <div className="w-full max-w-xs">
                  <RiskMeter score={report.score} band={report.band} />
                </div>
              </div>
              <Alert className="mt-5 border-amber-300 bg-amber-50 text-amber-950">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>{content.warning ?? "AI-assisted, not official verification"}</AlertTitle>
                <AlertDescription>{content.summary.plain_english}</AlertDescription>
              </Alert>
            </section>

            {report.is_stale ? (
              <Card className="border-amber-300 bg-amber-50">
                <CardContent className="space-y-4 p-5">
                  <div className="flex gap-3">
                    <RefreshCw className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
                    <div>
                      <h2 className="font-semibold text-amber-950">This report needs regeneration</h2>
                      <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-900">
                        {report.stale_reasons.map((reason) => <li key={reason}>- {reason}</li>)}
                      </ul>
                    </div>
                  </div>
                  <GenerateControls
                    accepted={acceptedDisclaimer}
                    disabled={working === "generating"}
                    label={working === "generating" ? "Regenerating..." : "Regenerate current report"}
                    onAcceptedChange={setAcceptedDisclaimer}
                    onGenerate={() => generateReport(true)}
                  />
                </CardContent>
              </Card>
            ) : null}

            {downloaded ? <SuccessState message="PDF downloaded." /> : null}

            <ReportSection icon={FileText} title="Case summary">
              <KeyValueGrid values={content.case_summary} />
            </ReportSection>

            <div className="grid gap-5 md:grid-cols-2">
              <ReportSection icon={UserRoundCheck} title="Buyer and seller details">
                <KeyValueGrid values={content.buyer_seller_details} />
              </ReportSection>
              <ReportSection icon={Landmark} title="Parcel/title details">
                <KeyValueGrid values={content.parcel_title_details} />
              </ReportSection>
            </div>

            <ReportSection icon={TableProperties} title="Documents reviewed">
              <RecordTable records={content.documents_reviewed ?? []} columns={["category", "filename", "status", "confidence_label"]} />
            </ReportSection>

            <ReportSection icon={FileText} title="Extracted information">
              <ExtractedInformation items={content.extracted_information ?? []} />
            </ReportSection>

            <div className="grid gap-5 lg:grid-cols-2">
              <ReportSection icon={FileWarning} title="Missing documents">
                <FindingList records={content.missing_documents ?? []} empty="No missing required documents were recorded." />
              </ReportSection>
              <ReportSection icon={AlertTriangle} title="Inconsistencies found">
                <FindingList records={content.inconsistencies_found ?? []} empty="No material inconsistencies were recorded." />
              </ReportSection>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <ReportSection icon={Search} title="Gazette search results">
                <GazetteSummary values={content.gazette_search_results} />
              </ReportSection>
              <ReportSection icon={ShieldCheck} title="Official search certificate review">
                <OfficialSearchSummary values={content.official_search_certificate_review} />
              </ReportSection>
            </div>

            <ReportSection icon={Scale} title="Detailed risk factors">
              <RiskFactorList factors={riskFactors} />
            </ReportSection>

            <ReportSection icon={ShieldCheck} title="Recommended next actions">
              {content.recommended_next_steps.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {content.recommended_next_steps.map((step) => (
                    <div key={step} className="rounded-md border bg-background/70 p-3 text-sm leading-6 text-muted-foreground">
                      {step}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">
                  No automated next action was recorded. Ask an advocate or surveyor to review the source evidence before completion.
                </p>
              )}
            </ReportSection>

            <div className="grid gap-5 lg:grid-cols-2">
              <ReportSection icon={FileText} title="Plain-English explanation">
                <p className="text-sm leading-6 text-muted-foreground">
                  {content.plain_english_explanation ?? content.summary.plain_english}
                </p>
              </ReportSection>
              <ReportSection icon={Languages} title="Optional Kiswahili summary">
                <p className="text-sm leading-6 text-muted-foreground">
                  {content.kiswahili_summary || content.summary.kiswahili || "Not requested for this case."}
                </p>
              </ReportSection>
            </div>

            <ReportSection icon={Scale} title="Legal disclaimer">
              <p className="text-sm leading-6 text-muted-foreground">{content.legal_disclaimer}</p>
            </ReportSection>

            <ReportSection icon={TableProperties} title="Appendix with evidence references">
              <RecordTable
                records={content.appendix_evidence_references ?? []}
                columns={["document_category", "field_name", "quote", "text_snippet"]}
                empty="No evidence references were attached."
              />
            </ReportSection>
          </motion.div>

          <aside className="space-y-4 lg:sticky lg:top-24 lg:h-fit">
            <Card className="premium-panel">
              <CardHeader><CardTitle>Risk score</CardTitle></CardHeader>
              <CardContent><RiskMeter score={report.score} band={report.band} /></CardContent>
            </Card>
            <Card className="premium-panel">
              <CardHeader><CardTitle>Download and share</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Button onClick={downloadReport} disabled={working === "downloading" || report.is_stale} className="w-full">
                  <Download className="h-4 w-4" />
                  {working === "downloading" ? "Preparing..." : "Download PDF"}
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`/cases/${params.caseId}/review?role=advocate&from=report`}>
                    <Share2 className="h-4 w-4" />
                    Share with advocate
                  </Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`/cases/${params.caseId}/review`}>
                    <UserRoundCheck className="h-4 w-4" />
                    Request expert review
                  </Link>
                </Button>
                {report.is_stale ? (
                  <p className="text-xs leading-5 text-amber-700">
                    Regenerate the report before downloading so the PDF matches the latest case evidence.
                  </p>
                ) : null}
              </CardContent>
            </Card>
            <Card className="border-primary/30 bg-primary/5">
              <CardContent className="flex gap-3 p-4">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                <p className="text-sm leading-6 text-muted-foreground">
                  The PDF is authenticated for the signed-in case owner and includes the report ID, timestamp, warning,
                  risk meter, recommendations, and evidence appendix.
                </p>
              </CardContent>
            </Card>
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}

function GenerateControls({
  accepted,
  disabled,
  label,
  onAcceptedChange,
  onGenerate
}: {
  accepted: boolean;
  disabled: boolean;
  label: string;
  onAcceptedChange: (value: boolean) => void;
  onGenerate: () => void;
}) {
  return (
    <div className="space-y-3">
      <label className="flex items-start gap-3 rounded-md border bg-background/80 p-3 text-sm leading-5">
        <input
          className="mt-1 h-4 w-4 shrink-0 accent-primary"
          type="checkbox"
          checked={accepted}
          onChange={(event) => onAcceptedChange(event.target.checked)}
        />
        <span>
          I understand this report is AI-assisted decision support, not legal advice, official registry proof, or a substitute for professional verification.
        </span>
      </label>
      <Button onClick={onGenerate} disabled={disabled || !accepted}>
        <RefreshCw className="h-4 w-4" />
        {label}
      </Button>
    </div>
  );
}

function ReportSection({
  children,
  icon: Icon,
  title
}: {
  children: React.ReactNode;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <Card className="premium-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function KeyValueGrid({ values }: { values?: ReportRecord }) {
  const entries = Object.entries(values ?? {});
  if (!entries.length) return <p className="text-sm text-muted-foreground">No information recorded.</p>;
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border bg-background/70 p-3">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label(key)}</dt>
          <dd className="mt-1 break-words text-sm leading-6">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function RecordTable({
  columns,
  empty = "No records available.",
  records
}: {
  records: ReportRecord[];
  columns: string[];
  empty?: string;
}) {
  if (!records.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full min-w-[620px] text-left text-sm">
        <thead className="bg-muted/70 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>{columns.map((column) => <th key={column} className="px-3 py-2 font-medium">{label(column)}</th>)}</tr>
        </thead>
        <tbody>
          {records.map((record, index) => (
            <tr key={`${record.document_id ?? record.category ?? index}`} className="border-t">
              {columns.map((column) => (
                <td key={column} className="max-w-[280px] px-3 py-3 align-top">
                  <span className="line-clamp-4 break-words text-muted-foreground">{formatValue(record[column])}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExtractedInformation({ items }: { items: NonNullable<ApiReport["content"]["extracted_information"]> }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No structured fields were extracted.</p>;
  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <div key={item.document_id ?? index} className="rounded-md border bg-background/70 p-4">
          <h3 className="font-medium">{item.document_label ?? "Uploaded document"}</h3>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {(item.fields ?? []).slice(0, 12).map((field) => (
              <div key={`${item.document_id}-${field.name}`} className="rounded-md bg-muted/40 p-2">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label(field.name)}</dt>
                <dd className="mt-1 break-words text-sm">{formatValue(field.value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

function FindingList({ empty, records }: { records: ReportRecord[]; empty: string }) {
  if (!records.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="space-y-3">
      {records.map((record, index) => {
        const severity = String(record.severity ?? "review");
        return (
          <div key={`${record.code ?? record.category ?? index}`} className={cn("rounded-md border p-3", severityClass(severity))}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-medium">{formatValue(record.label ?? record.category ?? record.code)}</h3>
              <Badge variant={severity === "critical" || severity === "high" ? "danger" : "warning"}>{severity}</Badge>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{formatValue(record.explanation ?? record.reason ?? record.summary)}</p>
          </div>
        );
      })}
    </div>
  );
}

function GazetteSummary({ values }: { values?: ApiReport["content"]["gazette_search_results"] }) {
  const notices = values?.notices ?? [];
  return (
    <div className="space-y-3">
      <KeyValueGrid values={{ status: values?.status, reason: values?.reason, query_terms: values?.query_terms }} />
      {notices.length ? (
        <RecordTable records={notices} columns={["source", "source_name", "title", "notice_title", "date", "publication_date"]} />
      ) : (
        <p className="text-sm text-muted-foreground">No Gazette notice matches were attached to this report.</p>
      )}
    </div>
  );
}

function OfficialSearchSummary({ values }: { values?: ApiReport["content"]["official_search_certificate_review"] }) {
  return (
    <div className="space-y-3">
      <KeyValueGrid
        values={{
          status: values?.official_search_status,
          verification_status: values?.verification_status,
          reason: values?.reason
        }}
      />
      {values?.certificate ? <KeyValueGrid values={values.certificate} /> : null}
      {values?.conflicts?.length ? <FindingList records={values.conflicts} empty="No conflicts recorded." /> : null}
    </div>
  );
}

function RiskFactorList({ factors }: { factors: ApiRiskFactor[] }) {
  if (!factors.length) return <p className="text-sm text-muted-foreground">No risk factors were recorded for this report.</p>;
  return (
    <div className="space-y-3">
      {factors.map((factor, index) => (
        <article key={`${factor.code}-${index}`} className={cn("rounded-md border p-4", severityClass(factor.severity))}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold">{factor.label}</h3>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{riskExplanation(factor)}</p>
            </div>
            <StatusBadge tone={severityTone(factor.severity)} label={`${factor.points} pts · ${factor.severity}`} />
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-[1fr_0.85fr]">
            <div className="rounded-md border bg-background/70 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recommended action</div>
              <p className="mt-2 text-sm leading-6">{factor.recommendation}</p>
            </div>
            <div className="rounded-md border bg-background/70 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evidence</div>
              <div className="mt-2 space-y-1 text-sm text-muted-foreground">{renderEvidence(factor.evidence)}</div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function severityTone(severity: string) {
  if (severity === "critical" || severity === "high") return "high_risk" as const;
  if (severity === "medium") return "needs_review" as const;
  return "not_verified" as const;
}

function severityClass(severity: string) {
  if (severity === "critical") return "border-red-300 bg-red-50";
  if (severity === "high") return "border-orange-300 bg-orange-50";
  if (severity === "medium") return "border-amber-300 bg-amber-50";
  return "bg-background/70";
}

function riskExplanation(factor: ApiRiskFactor) {
  const explanations: Record<string, string> = {
    parcel_number_mismatch: "The parcel identifier should stay consistent across every document in the transaction packet.",
    missing_title_deed: "The title deed is the core ownership document; without it the rest of the packet cannot be trusted.",
    missing_parcel_or_title_number: "A transaction cannot be safely matched to land records if the title or parcel number is missing.",
    seller_name_mismatch: "The person selling should match the owner or authorized party shown in supporting evidence.",
    id_mismatch: "Identity inconsistencies can indicate a wrong party, typo, forged document, or incomplete verification.",
    missing_official_land_search: "A buyer should not rely only on private documents when a fresh official search is missing.",
    stale_search_certificate: "Older searches may miss recent cautions, charges, restrictions, or ownership changes.",
    sale_agreement_before_search: "Signing or dating an agreement before verification increases exposure to hidden issues.",
    missing_consent_to_transfer: "Transfer consent is often essential before a deal can safely proceed.",
    gazette_notice_conflict: "Gazette notices can indicate loss, rectification, restriction, revocation, or other public-record risk.",
    caution_restriction_charge: "Cautions, restrictions, and charges can block or complicate transfer.",
    payment_before_verification: "Money moving before verification is complete raises avoidable buyer exposure.",
    duplicate_parcel_number: "Duplicate parcel references may indicate conflicting records or a reused document packet."
  };
  return explanations[factor.code] ?? "This signal needs review because it may affect buyer confidence before signing or paying.";
}

function renderEvidence(evidence: Record<string, unknown>) {
  const entries = Object.entries(evidence ?? {});
  if (!entries.length) return <p>No structured evidence attached.</p>;
  return entries.slice(0, 4).map(([key, value]) => (
    <p key={key} className="break-words">
      <span className="font-medium text-foreground">{label(key)}:</span> {formatValue(value)}
    </p>
  ));
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (Array.isArray(value)) return value.length ? value.map(formatValue).join(", ") : "None recorded";
  if (typeof value === "object") {
    const entries = Object.entries(value as ReportRecord)
      .filter(([, item]) => item !== null && item !== undefined && item !== "" && !(Array.isArray(item) && item.length === 0))
      .slice(0, 5);
    return entries.length ? entries.map(([key, item]) => `${label(key)}: ${formatValue(item)}`).join("; ") : "No details recorded";
  }
  return String(value).replaceAll("_", " ");
}

function label(value: string) {
  const text = value.replaceAll("_", " ").trim();
  return text ? text[0].toUpperCase() + text.slice(1) : "Not recorded";
}

function humanError(error: string) {
  if (error.includes("Report is stale")) return "Report is stale. Regenerate it before downloading.";
  if (error.includes("Legal disclaimer acceptance")) return "Accept the disclaimer before generating the report.";
  return error;
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import { ArrowRight, BrainCircuit, ExternalLink, FileSearch, Gavel, Landmark, Newspaper, Scale, ShieldCheck, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { CaseAgentChat } from "@/components/case-agent-chat";
import { ProgressTracker } from "@/components/progress-tracker";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge } from "@/components/status-badge";
import { SuccessState } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiFetch, type ApiGazetteSearch, type ApiReport } from "@/lib/api";

const agentSteps = [
  { name: "IntakeAgent", body: "Confirms case context and uploaded evidence.", icon: FileSearch },
  { name: "VisionExtractionAgent", body: "Reads parcels, names, IDs, dates, maps, seals, and quality signals.", icon: Sparkles },
  { name: "ConsistencyAgent", body: "Compares parcel, seller, owner, registry, dates, and parties.", icon: Landmark },
  { name: "RiskScoringAgent", body: "Applies explicit risk factors and score bands.", icon: Scale },
  { name: "LegalSafetyAgent", body: "Checks the wording does not overclaim legal or official verification.", icon: Gavel }
];

export default function AnalysisPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAppAuth();
  const [report, setReport] = useState<ApiReport | null>(null);
  const [gazette, setGazette] = useState<ApiGazetteSearch | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "complete">("idle");
  const [gazetteStatus, setGazetteStatus] = useState<"idle" | "running" | "complete">("idle");
  const [error, setError] = useState("");
  const [acceptedLegalDisclaimer, setAcceptedLegalDisclaimer] = useState(false);

  async function runAnalysis() {
    setStatus("running");
    setError("");
    if (!acceptedLegalDisclaimer) {
      setStatus("idle");
      setError("Accept the legal disclaimer before generating a report.");
      return;
    }
    try {
      const token = await getToken();
      setReport(await apiFetch<ApiReport>(`/cases/${params.caseId}/analysis`, token, {
        method: "POST",
        body: JSON.stringify({ accepted_legal_disclaimer: acceptedLegalDisclaimer })
      }));
      setStatus("complete");
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Analysis failed");
    }
  }

  async function runGazetteSearch() {
    setGazetteStatus("running");
    setError("");
    try {
      const token = await getToken();
      setGazette(await apiFetch<ApiGazetteSearch>(`/api/cases/${params.caseId}/gazette-search`, token, { method: "POST" }));
      setGazetteStatus("complete");
    } catch (err) {
      setGazetteStatus("idle");
      setError(err instanceof Error ? err.message : "Gazette search failed");
    }
  }

  const progress = status === "complete" ? 100 : status === "running" ? 68 : 18;

  return (
    <AppShell>
      <ProgressTracker current="analysis" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_370px]">
        <div className="space-y-5">
          <div>
            <p className="text-sm font-medium text-primary">AI due diligence</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Case analysis</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Run the multi-agent review once documents are uploaded and extraction has been checked. The report separates observed evidence from official verification.
            </p>
          </div>

          <Card className="premium-panel overflow-hidden">
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <CardTitle className="flex items-center gap-2">
                  <BrainCircuit className="h-5 w-5 text-primary" aria-hidden="true" />
                  Agent orchestration
                </CardTitle>
                <StatusBadge
                  tone={status === "complete" ? "success" : status === "running" ? "neutral" : "not_verified"}
                  label={status === "complete" ? "Analysis complete" : status === "running" ? "Agents running" : "Ready to run"}
                />
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <Progress value={progress} aria-label="Analysis progress" />
              <div className="grid gap-3 md:grid-cols-2">
                {agentSteps.map((step, index) => {
                  const Icon = step.icon;
                  const active = status === "running" || status === "complete";
                  return (
                    <motion.div
                      key={step.name}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.04 }}
                      className="rounded-lg border bg-background/70 p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                        <span className="text-xs text-muted-foreground">{active ? "Queued" : "Waiting"}</span>
                      </div>
                      <h2 className="mt-3 font-semibold">{step.name}</h2>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.body}</p>
                    </motion.div>
                  );
                })}
              </div>
              {status === "complete" ? <SuccessState message="Risk report generated and audit events recorded." /> : null}
              {error ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              ) : null}
              <label className="flex items-start gap-3 rounded-md border bg-muted/40 p-3 text-sm leading-5">
                <input
                  className="mt-1 h-4 w-4 shrink-0 accent-primary"
                  type="checkbox"
                  checked={acceptedLegalDisclaimer}
                  onChange={(event) => setAcceptedLegalDisclaimer(event.target.checked)}
                />
                <span>
                  I understand this report is AI-assisted decision support, not legal advice, official registry proof, or a substitute for an advocate, surveyor, official land search, or Ministry/NLC confirmation.
                </span>
              </label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Button onClick={runAnalysis} disabled={status === "running" || !acceptedLegalDisclaimer}>
                  <BrainCircuit className="h-4 w-4" />
                  {status === "running" ? "Running analysis..." : "Run risk analysis"}
                </Button>
                {report ? (
                  <Button asChild variant="outline">
                    <Link href={`/cases/${params.caseId}/report`}>Open report <ArrowRight className="h-4 w-4" /></Link>
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card className="premium-panel overflow-hidden">
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <CardTitle className="flex items-center gap-2">
                  <Newspaper className="h-5 w-5 text-primary" aria-hidden="true" />
                  Kenya Gazette search
                </CardTitle>
                <StatusBadge tone={gazetteTone(gazette?.status)} label={gazetteLabel(gazette?.status, gazetteStatus)} />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-muted-foreground">
                Search configured Gazette sources using parcel, title, LR number, owner, county, registry, and location terms. Gazette search is only one risk signal and does not replace official due diligence.
              </p>
              <Button onClick={runGazetteSearch} disabled={gazetteStatus === "running"} variant="outline">
                <Newspaper className="h-4 w-4" />
                {gazetteStatus === "running" ? "Searching Gazette..." : "Run Gazette search"}
              </Button>

              {gazette ? (
                <div className="space-y-3">
                  <div className="rounded-lg border bg-muted/40 p-4">
                    <div className="font-medium">{gazette.message}</div>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">{gazette.disclaimer}</p>
                    {gazette.query_terms.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {gazette.query_terms.slice(0, 10).map((term) => (
                          <span key={term} className="rounded-md border bg-background px-2 py-1 text-xs">{term}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  {gazette.results.length ? (
                    <div className="grid gap-3">
                      {gazette.results.map((result, index) => (
                        <article key={`${result.source_url}-${index}`} className="rounded-lg border bg-background/70 p-4">
                          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
                            <div>
                              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{result.source_name}</div>
                              <h2 className="mt-1 font-semibold">{result.notice_title}</h2>
                              <p className="mt-2 text-sm leading-6 text-muted-foreground">{result.snippet}</p>
                            </div>
                            <a className="inline-flex items-center gap-1 text-sm font-medium text-primary" href={result.source_url} target="_blank" rel="noreferrer">
                              Source <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span>{Math.round(result.confidence_score * 100)}% confidence</span>
                            {result.publication_date ? <span>{result.publication_date}</span> : null}
                            {result.matched_keywords.map((keyword) => <span key={keyword}>#{keyword}</span>)}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border bg-background/70 p-4 text-sm text-muted-foreground">{gazetteEmptyCopy(gazette.status)}</div>
                  )}
                  <div className="grid gap-2 sm:grid-cols-2">
                    {gazette.source_results.map((source) => (
                      <div key={source.source_name} className="rounded-md border bg-muted/30 p-3 text-sm">
                        <div className="font-medium">{source.source_name}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{source.status.replaceAll("_", " ")}</div>
                        {source.error ? <div className="mt-2 text-xs text-destructive">{source.error}</div> : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="flex gap-3 p-5">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="text-sm leading-6 text-muted-foreground">
                If an official source is unavailable, the system keeps the status as not verified from official source, parses uploaded official search certificates, or routes the file to manual review.
              </p>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:h-fit">
          <Card className="premium-panel">
            <CardHeader><CardTitle>Latest result</CardTitle></CardHeader>
            <CardContent>
              {report ? (
                <RiskMeter score={report.score} band={report.band} />
              ) : (
                <div className="rounded-lg border bg-muted/40 p-5 text-sm leading-6 text-muted-foreground">
                  No report generated in this session yet. Run analysis after extraction review.
                </div>
              )}
            </CardContent>
          </Card>
          <Button asChild variant="outline" className="w-full"><Link href={`/cases/${params.caseId}/timeline`}>View timeline</Link></Button>
          <CaseAgentChat caseId={params.caseId} />
        </aside>
      </div>
    </AppShell>
  );
}

function gazetteTone(status?: ApiGazetteSearch["status"]) {
  if (status === "checked_match_found") return "high_risk" as const;
  if (status === "checked_no_match") return "verified" as const;
  if (status === "search_failed" || status === "manual_review_required") return "needs_review" as const;
  if (status === "not_configured") return "not_verified" as const;
  return "neutral" as const;
}

function gazetteLabel(status: ApiGazetteSearch["status"] | undefined, runningStatus: "idle" | "running" | "complete") {
  if (runningStatus === "running") return "Searching";
  if (!status) return "Not checked";
  if (status === "checked_match_found") return "Possible match found";
  if (status === "checked_no_match") return "No match found";
  if (status === "search_failed") return "Search failed";
  if (status === "manual_review_required") return "Manual review required";
  return "Not configured";
}

function gazetteEmptyCopy(status: ApiGazetteSearch["status"]) {
  if (status === "checked_no_match") return "No Gazette match was found in configured sources.";
  if (status === "search_failed") return "Automated Gazette search failed. Route this case to manual review.";
  if (status === "not_configured") return "No Gazette source adapter is configured for automated search.";
  if (status === "manual_review_required") return "The system needs more parcel, title, owner, county, registry, or location terms before searching.";
  return "No normalized Gazette notices are available.";
}

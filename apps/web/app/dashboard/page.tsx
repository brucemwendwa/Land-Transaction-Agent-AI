"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAppAuth } from "@/lib/auth";
import { AlertTriangle, ArrowRight, FileCheck2, Plus, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CaseCard } from "@/components/case-card";
import { apiFetch, type ApiCase } from "@/lib/api";
import { DashboardSkeleton } from "@/components/dashboard-skeleton";
import { EmptyState, ErrorState } from "@/components/state-views";

export default function DashboardPage() {
  const { getToken } = useAppAuth();
  const [cases, setCases] = useState<ApiCase[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const token = await getToken();
        setCases(await apiFetch<ApiCase[]>("/cases", token));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load cases");
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Buyer command center</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Land transaction cases</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Track upload readiness, review status, and risk-report progress across active transactions.
          </p>
        </div>
        <Button asChild><Link href="/cases/new"><Plus className="h-4 w-4" /> New case</Link></Button>
      </div>

      {loading ? <DashboardSkeleton /> : null}

      {!loading && error ? <ErrorState message={error} onRetry={() => window.location.reload()} /> : null}

      {!loading && !error ? (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-3">
            {[
              { label: "Total cases", value: cases.length, icon: ShieldCheck },
              { label: "Reports ready", value: cases.filter((item) => item.status === "report_ready").length, icon: FileCheck2 },
              { label: "Manual review", value: cases.filter((item) => item.status === "manual_review").length, icon: AlertTriangle }
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <Card key={stat.label} className="premium-panel">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                      {stat.label}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-3xl font-semibold">{stat.value}</CardContent>
                </Card>
              );
            })}
          </div>

          <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <Card className="premium-panel">
              <CardHeader>
                <CardTitle className="text-base">Next best action</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{nextActionCopy(cases)}</p>
                <Button asChild variant="outline" className="w-full sm:w-auto">
                  <Link href={nextActionHref(cases)}>
                    Continue
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
            <Card className="premium-panel">
              <CardHeader>
                <CardTitle className="text-base">High-attention cases</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold">
                  {cases.filter((item) => item.risk_level === "high" || item.risk_level === "critical").length}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  High or critical scores should be reviewed by an advocate, surveyor, or lender before funds move.
                </p>
              </CardContent>
            </Card>
          </div>

          {cases.length ? (
            <motion.div className="grid gap-4 lg:grid-cols-2" initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05 } } }}>
              {cases.map((landCase) => (
                <motion.div key={landCase.id} variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}>
                  <CaseCard landCase={landCase} />
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <EmptyState
              title="Start with a transaction case"
              description="Create a case, upload documents, and generate a risk report before signing or releasing funds."
              action={<Button asChild><Link href="/cases/new">Create case</Link></Button>}
            />
          )}
        </>
      ) : null}
    </AppShell>
  );
}

function nextActionCopy(cases: ApiCase[]) {
  if (!cases.length) return "Create your first transaction case and upload the core diligence packet.";
  const needsDocuments = cases.find((item) => item.documents.length === 0);
  if (needsDocuments) return `Upload documents for ${needsDocuments.title} so extraction and risk scoring can start.`;
  const ready = cases.find((item) => item.status === "ready_for_analysis");
  if (ready) return `Run analysis for ${ready.title}; the document set is ready for the risk engine.`;
  const review = cases.find((item) => item.status === "manual_review");
  if (review) return `${review.title} needs expert review before the buyer relies on the result.`;
  return "Review the latest reports and regenerate any stale reports before sharing PDF copies.";
}

function nextActionHref(cases: ApiCase[]) {
  if (!cases.length) return "/cases/new";
  const needsDocuments = cases.find((item) => item.documents.length === 0);
  if (needsDocuments) return `/cases/${needsDocuments.id}/upload`;
  const ready = cases.find((item) => item.status === "ready_for_analysis");
  if (ready) return `/cases/${ready.id}/analysis`;
  const review = cases.find((item) => item.status === "manual_review");
  if (review) return `/cases/${review.id}/review`;
  return `/cases/${cases[0].id}/report`;
}

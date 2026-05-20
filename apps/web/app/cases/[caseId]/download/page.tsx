"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { ArrowLeft, Download, FileCheck2, Share2, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { SuccessState } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { apiUrl } from "@/lib/api";

export default function DownloadReportPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAuth();
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function download() {
    setStatus("Preparing PDF...");
    setError("");
    setLoading(true);
    try {
      const token = await getToken();
      const response = await fetch(apiUrl(`/cases/${params.caseId}/report.pdf`), {
        headers: token ? { authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) {
        const detail = await response.text();
        setStatus("");
        setError(
          detail.includes("Report is stale")
            ? "Regenerate the report before downloading the PDF."
            : "PDF is not ready yet. Generate the report first, then try again."
        );
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mradi-wa-ardhi-${params.caseId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setStatus("Downloaded");
    } catch (err) {
      setStatus("");
      setError(err instanceof Error ? err.message : "Unable to download report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="premium-panel">
          <CardHeader>
            <Button asChild variant="ghost" className="mb-3 w-fit px-0 hover:bg-transparent">
              <Link href={`/cases/${params.caseId}/report`}><ArrowLeft className="h-4 w-4" /> Back to report</Link>
            </Button>
            <CardTitle className="flex items-center gap-2 text-3xl">
              <Download className="h-6 w-6 text-primary" aria-hidden="true" />
              Download report
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Download the signed-in buyer&apos;s current case report as a PDF for sharing with an advocate, surveyor, bank, SACCO, or family decision-maker.
            </p>
            {loading ? (
              <div className="space-y-2" aria-live="polite">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{status}</span>
                  <span>Working</span>
                </div>
                <Progress value={72} />
              </div>
            ) : null}
            {status === "Downloaded" ? <SuccessState message="PDF downloaded." /> : null}
            {error ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            ) : null}
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button onClick={download} disabled={loading}><Download className="h-4 w-4" /> {loading ? "Preparing..." : "Download PDF"}</Button>
              <Button asChild variant="outline">
                <Link href={`/cases/${params.caseId}/review?role=advocate&from=download`}>
                  <Share2 className="h-4 w-4" /> Share with advocate
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <aside className="space-y-4">
          <Card className="premium-panel">
            <CardContent className="flex gap-3 p-4">
              <FileCheck2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="text-sm leading-6 text-muted-foreground">
                The PDF includes the score, evidence, recommendations, official-source status, and legal safety disclaimer.
              </p>
            </CardContent>
          </Card>
          <Card className="premium-panel">
            <CardContent className="flex gap-3 p-4">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="text-sm leading-6 text-muted-foreground">
                Share the PDF with reviewers, but treat it as decision support, not legal advice or official registry proof.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </AppShell>
  );
}

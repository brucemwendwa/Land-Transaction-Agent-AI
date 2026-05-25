"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import { ArrowLeft, Download, FileCheck2, Share2, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { SuccessState } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { apiFetch, apiUrl, type MpesaPaymentInitiateResponse, type PaymentRead } from "@/lib/api";

const reportUnlockAmount = Number(process.env.NEXT_PUBLIC_REPORT_UNLOCK_AMOUNT ?? 0);

export default function DownloadReportPage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAppAuth();
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [paymentRequired, setPaymentRequired] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [payment, setPayment] = useState<PaymentRead | null>(null);
  const [paymentMessage, setPaymentMessage] = useState("");
  const [paymentLoading, setPaymentLoading] = useState(false);

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
        if (response.status === 402 || detail.includes("Payment is required")) {
          setPaymentRequired(true);
          setError("Payment is required before this report can be downloaded.");
          return;
        }
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

  async function initiatePayment() {
    if (!reportUnlockAmount) {
      setPaymentMessage("Report unlock pricing is not configured for this deployment.");
      return;
    }
    if (!phoneNumber.trim()) {
      setPaymentMessage("Enter the M-Pesa phone number to receive the STK Push.");
      return;
    }
    setPaymentLoading(true);
    setPaymentMessage("");
    try {
      const token = await getToken();
      const response = await apiFetch<MpesaPaymentInitiateResponse>("/payments/mpesa/stk-push", token, {
        method: "POST",
        body: JSON.stringify({
          case_id: params.caseId,
          amount: reportUnlockAmount,
          phone_number: phoneNumber,
          purpose: "report_unlock"
        })
      });
      setPayment(response.payment);
      setPaymentMessage(response.message);
    } catch (err) {
      setPaymentMessage(err instanceof Error ? err.message : "Unable to initiate M-Pesa payment");
    } finally {
      setPaymentLoading(false);
    }
  }

  async function pollPaymentStatus() {
    if (!payment) return;
    setPaymentLoading(true);
    setPaymentMessage("");
    try {
      const token = await getToken();
      const latest = await apiFetch<PaymentRead>(`/payments/${payment.id}`, token);
      setPayment(latest);
      setPaymentMessage(
        latest.status === "successful"
          ? "Payment confirmed. You can download the report."
          : `Payment status: ${latest.status.replaceAll("_", " ")}`
      );
      if (latest.status === "successful") {
        setPaymentRequired(false);
        setError("");
      }
    } catch (err) {
      setPaymentMessage(err instanceof Error ? err.message : "Unable to check payment status");
    } finally {
      setPaymentLoading(false);
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
            {paymentRequired || payment ? (
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="text-sm font-medium">M-Pesa report unlock</div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Reports remain locked until Daraja confirms a successful payment callback. Missing M-Pesa credentials show a transparent not-configured status.
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
                  <div>
                    <Label htmlFor="mpesa-phone">M-Pesa phone number</Label>
                    <Input
                      id="mpesa-phone"
                      className="mt-1"
                      value={phoneNumber}
                      placeholder="07..."
                      onChange={(event) => setPhoneNumber(event.target.value)}
                    />
                  </div>
                  <Button onClick={initiatePayment} disabled={paymentLoading || !reportUnlockAmount}>
                    {paymentLoading ? "Starting..." : `Pay KES ${reportUnlockAmount || "not configured"}`}
                  </Button>
                </div>
                {payment ? (
                  <div className="mt-4 flex flex-col gap-3 rounded-md border bg-background/70 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <span>Status: {payment.status.replaceAll("_", " ")}</span>
                    <Button variant="outline" onClick={pollPaymentStatus} disabled={paymentLoading}>
                      {paymentLoading ? "Checking..." : "Check status"}
                    </Button>
                  </div>
                ) : null}
                {paymentMessage ? <p className="mt-3 text-sm leading-6 text-muted-foreground">{paymentMessage}</p> : null}
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

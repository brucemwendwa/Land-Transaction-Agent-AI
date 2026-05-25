"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import { reviewRoles, type ReviewRole } from "@mradi/contracts";
import { ArrowLeft, ClipboardCheck, Gavel, MapPinned, UserRoundCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { SuccessState } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";

export default function ReviewRequestPage() {
  const params = useParams<{ caseId: string }>();
  const searchParams = useSearchParams();
  const { getToken } = useAppAuth();
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestedRole = searchParams.get("role");
  const reviewerRole: ReviewRole = reviewRoles.includes(requestedRole as ReviewRole) ? (requestedRole as ReviewRole) : "advocate";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setStatus("");
    const form = new FormData(event.currentTarget);
    try {
      const token = await getToken();
      await apiFetch("/reviews", token, {
        method: "POST",
        body: JSON.stringify({
          case_id: params.caseId,
          reviewer_role: form.get("reviewer_role"),
          reviewer_email: form.get("reviewer_email"),
          note: form.get("note")
        })
      });
      setStatus("Review request saved and audit logged.");
      event.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request review");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <Button asChild variant="ghost" className="mb-5">
            <Link href={`/cases/${params.caseId}/report`}><ArrowLeft className="h-4 w-4" /> Back to report</Link>
          </Button>
          <div className="mb-6">
            <p className="text-sm font-medium text-primary">Human expert review</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Request expert help</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Route the case to a professional workflow when official verification is incomplete, risk is high, a site visit is needed, or boundary and consent questions need expert judgment.
            </p>
          </div>
          <Card className="premium-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRoundCheck className="h-5 w-5 text-primary" aria-hidden="true" />
                Reviewer details
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="reviewer_role">Reviewer type</Label>
                  <Select id="reviewer_role" name="reviewer_role" defaultValue={reviewerRole}>
                    {reviewRoles.map((role) => (
                      <option key={role} value={role}>{reviewRoleLabel(role)}</option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="reviewer_email">Reviewer email</Label>
                  <Input id="reviewer_email" name="reviewer_email" type="email" required placeholder="reviewer@example.com" />
                </div>
                <div>
                  <Label htmlFor="note">Note</Label>
                  <Textarea
                    id="note"
                    name="note"
                    placeholder="Summarize what you need: advocate review, surveyor review, site visit, boundary verification, official search assistance..."
                  />
                </div>
                {status ? <SuccessState message={status} /> : null}
                {error ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                    {error}
                  </div>
                ) : null}
                <Button type="submit" disabled={loading}>{loading ? "Saving request..." : "Request review"}</Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:h-fit">
          {[
            { icon: Gavel, title: "Advocate review", body: "Best for agreements, consents, POA, ownership evidence, and legal transfer conditions." },
            { icon: MapPinned, title: "Surveyor and boundary help", body: "Best for maps, mutation forms, boundaries, acreage, beacons, site visits, and parcel identity questions." },
            { icon: ClipboardCheck, title: "Official search assistance", body: "Use when a fresh search certificate is missing, stale, or needs professional follow-up." }
          ].map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.title} className="premium-panel">
                <CardContent className="flex gap-3 p-4">
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                  <div>
                    <div className="font-medium">{item.title}</div>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.body}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </aside>
      </div>
    </AppShell>
  );
}

function reviewRoleLabel(role: ReviewRole) {
  const labels: Record<ReviewRole, string> = {
    advocate: "Advocate review",
    surveyor: "Surveyor review",
    site_visit: "Site visit",
    boundary_verification: "Boundary verification",
    official_search_assistance: "Official search assistance"
  };
  return labels[role];
}

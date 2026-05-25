"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, ClipboardCheck, Gavel, MapPinned, Save } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingPanel, SuccessState } from "@/components/state-views";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAppAuth } from "@/lib/auth";
import { apiFetch, type ReviewRequest } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const statuses = ["assigned", "in_review", "completed", "rejected"];

export default function ExpertDashboardPage() {
  const { getToken } = useAppAuth();
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [drafts, setDrafts] = useState<Record<string, { status: string; review_summary: string; recommendation: string; attachment_document_ids: string }>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const token = await getToken();
    const loaded = await apiFetch<ReviewRequest[]>("/reviews/assigned", token);
    setReviews(loaded);
    setDrafts(
      Object.fromEntries(
        loaded.map((review) => [
          review.id,
          {
            status: review.status,
            review_summary: review.review_summary,
            recommendation: review.recommendation,
            attachment_document_ids: Array.isArray(review.metadata_json.attachment_document_ids)
              ? review.metadata_json.attachment_document_ids.join(", ")
              : ""
          }
        ])
      )
    );
    setLoading(false);
  }, [getToken]);

  useEffect(() => {
    void load().catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load assigned reviews");
      setLoading(false);
    });
  }, [load]);

  async function save(review: ReviewRequest) {
    setSavingId(review.id);
    setError("");
    setSuccess("");
    try {
      const token = await getToken();
      const draft = drafts[review.id];
      await apiFetch(`/reviews/${review.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          status: draft.status,
          review_summary: draft.review_summary,
          recommendation: draft.recommendation,
          attachment_document_ids: draft.attachment_document_ids
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
        })
      });
      setSuccess("Expert review updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save review");
    } finally {
      setSavingId("");
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Assigned expert work</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Expert dashboard</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Review only assigned land cases, add professional notes, and record a clear recommendation for the buyer workflow.
          </p>
        </div>
        <Button asChild variant="outline"><Link href="/reviews">All review requests</Link></Button>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading assigned reviews" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} onRetry={() => void load()} /></div> : null}
      {success ? <SuccessState className="mt-6" message={success} /> : null}
      {!loading && !error && !reviews.length ? (
        <div className="mt-6">
          <EmptyState title="No assigned reviews" description="Assigned advocate, surveyor, site visit, boundary, and official-search assistance requests will appear here." />
        </div>
      ) : null}

      {reviews.length ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {reviews.map((review) => {
            const Icon = review.reviewer_role === "surveyor" ? MapPinned : Gavel;
            const draft = drafts[review.id] ?? {
              status: review.status,
              review_summary: review.review_summary,
              recommendation: review.recommendation,
              attachment_document_ids: Array.isArray(review.metadata_json.attachment_document_ids)
                ? review.metadata_json.attachment_document_ids.join(", ")
                : ""
            };
            return (
              <Card key={review.id} className="premium-panel">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 capitalize">
                      <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                      {review.reviewer_role.replaceAll("_", " ")}
                    </CardTitle>
                    <StatusBadge tone={statusToneFromValue(review.status)} label={review.status.replaceAll("_", " ")} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                    <div className="font-medium">{review.reviewer_email}</div>
                    <div className="mt-1 text-xs text-muted-foreground">Requested {formatDate(review.created_at)}</div>
                    <p className="mt-3 leading-6 text-muted-foreground">{review.note || "No requester note provided."}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor={`status-${review.id}`}>Review status</label>
                    <Select
                      id={`status-${review.id}`}
                      className="mt-1"
                      value={draft.status}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [review.id]: { ...draft, status: event.target.value }
                        }))
                      }
                    >
                      {statuses.map((status) => (
                        <option key={status} value={status}>{status.replaceAll("_", " ")}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor={`summary-${review.id}`}>Review notes</label>
                    <Textarea
                      id={`summary-${review.id}`}
                      className="mt-1"
                      rows={4}
                      value={draft.review_summary}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [review.id]: { ...draft, review_summary: event.target.value }
                        }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor={`recommendation-${review.id}`}>Recommendation</label>
                    <Textarea
                      id={`recommendation-${review.id}`}
                      className="mt-1"
                      rows={3}
                      value={draft.recommendation}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [review.id]: { ...draft, recommendation: event.target.value }
                        }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor={`attachments-${review.id}`}>Uploaded attachment document IDs</label>
                    <Input
                      id={`attachments-${review.id}`}
                      className="mt-1"
                      value={draft.attachment_document_ids}
                      placeholder="Comma-separated document IDs"
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [review.id]: { ...draft, attachment_document_ids: event.target.value }
                        }))
                      }
                    />
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button onClick={() => void save(review)} disabled={savingId === review.id}>
                      {draft.status === "completed" ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
                      {savingId === review.id ? "Saving..." : "Save review"}
                    </Button>
                    <Button asChild variant="outline">
                      <Link href={`/cases/${review.case_id}/timeline`}>
                        <ClipboardCheck className="h-4 w-4" /> Case timeline <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}
    </AppShell>
  );
}

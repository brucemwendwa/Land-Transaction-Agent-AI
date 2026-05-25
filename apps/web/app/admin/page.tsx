"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAppAuth } from "@/lib/auth";
import { AlertTriangle, ClipboardList, ShieldCheck, UserRoundCheck, Users } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { ErrorState, LoadingPanel } from "@/components/state-views";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { apiFetch, type ApiCase, type ReviewRequest } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

export default function AdminPage() {
  const { getToken } = useAppAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [cases, setCases] = useState<ApiCase[]>([]);
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [assignmentTargets, setAssignmentTargets] = useState<Record<string, string>>({});
  const [assigningId, setAssigningId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const token = await getToken();
        const [loadedUsers, loadedCases, loadedReviews] = await Promise.all([
          apiFetch<AdminUser[]>("/admin/users", token),
          apiFetch<ApiCase[]>("/admin/cases", token),
          apiFetch<ReviewRequest[]>("/reviews", token)
        ]);
        setUsers(loadedUsers);
        setCases(loadedCases);
        setReviews(loadedReviews);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Admin access unavailable");
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  const experts = users.filter((user) => ["advocate", "surveyor", "admin"].includes(user.role));

  async function assignReview(review: ReviewRequest) {
    const assignedTo = assignmentTargets[review.id];
    if (!assignedTo) {
      setError("Choose an expert before assigning the review.");
      return;
    }
    setAssigningId(review.id);
    setError("");
    try {
      const token = await getToken();
      const updated = await apiFetch<ReviewRequest>(`/reviews/${review.id}/assign`, token, {
        method: "POST",
        body: JSON.stringify({ assigned_to_user_id: assignedTo })
      });
      setReviews((current) => current.map((item) => (item.id === review.id ? updated : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to assign review");
    } finally {
      setAssigningId("");
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Operational control</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Admin dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Monitor users, cases, manual-review load, and verification posture across the platform.
          </p>
        </div>
        <Button asChild variant="outline"><Link href="/audit-log">Open audit log</Link></Button>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading admin workspace" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} /></div> : null}

      {!loading && !error ? (
        <>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Users", value: users.length, icon: Users },
              { label: "Cases", value: cases.length, icon: ClipboardList },
              { label: "Manual review", value: cases.filter((item) => item.status === "manual_review").length, icon: AlertTriangle },
              {
                label: "Scanner not configured",
                value: cases.flatMap((item) => item.documents).filter((document) => document.scan_status === "not_configured").length,
                icon: AlertTriangle
              }
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

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Card className="premium-panel">
              <CardHeader><CardTitle>Recent users</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {users.length ? users.map((user, index) => (
                  <motion.div
                    key={user.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.03 }}
                    className="flex items-center justify-between gap-3 rounded-lg border bg-background/70 p-3"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{user.full_name || user.email}</div>
                      <div className="truncate text-xs text-muted-foreground">{user.email}</div>
                      <div className="mt-1 text-xs text-muted-foreground">Joined {formatDate(user.created_at)}</div>
                    </div>
                    <Badge variant="outline">{user.role}</Badge>
                  </motion.div>
                )) : (
                  <EmptyInline icon={<Users className="h-5 w-5" />} text="No users returned for this admin scope." />
                )}
              </CardContent>
            </Card>
            <Card className="premium-panel">
              <CardHeader><CardTitle>Recent cases</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {cases.length ? cases.map((landCase, index) => (
                  <motion.div
                    key={landCase.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.03 }}
                    className="flex items-center justify-between gap-3 rounded-lg border bg-background/70 p-3"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{landCase.title}</div>
                      <div className="truncate text-xs text-muted-foreground">{landCase.parcel_number_claimed || "No parcel recorded"}</div>
                    </div>
                    <StatusBadge tone={statusToneFromValue(landCase.status)} label={landCase.status.replaceAll("_", " ")} />
                  </motion.div>
                )) : (
                  <EmptyInline icon={<ClipboardList className="h-5 w-5" />} text="Cases created by buyers and teams will appear here for review and governance." />
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="premium-panel mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRoundCheck className="h-5 w-5 text-primary" aria-hidden="true" />
                Assign expert reviews
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {reviews.length && experts.length ? reviews.map((review) => (
                <div key={review.id} className="grid gap-3 rounded-lg border bg-background/70 p-3 md:grid-cols-[1fr_240px_auto] md:items-center">
                  <div className="min-w-0">
                    <div className="truncate font-medium capitalize">{review.reviewer_role.replaceAll("_", " ")} review</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Case {review.case_id.slice(0, 8)} · {review.status.replaceAll("_", " ")} · {review.reviewer_email}
                    </div>
                  </div>
                  <Select
                    aria-label={`Assign expert for review ${review.id}`}
                    value={assignmentTargets[review.id] ?? review.assigned_to_user_id ?? ""}
                    onChange={(event) =>
                      setAssignmentTargets((current) => ({ ...current, [review.id]: event.target.value }))
                    }
                  >
                    <option value="">Choose expert</option>
                    {experts.map((expert) => (
                      <option key={expert.id} value={expert.id}>
                        {expert.full_name || expert.email} ({expert.role})
                      </option>
                    ))}
                  </Select>
                  <Button onClick={() => void assignReview(review)} disabled={assigningId === review.id}>
                    {assigningId === review.id ? "Assigning..." : "Assign"}
                  </Button>
                </div>
              )) : (
                <EmptyInline
                  icon={<UserRoundCheck className="h-5 w-5" />}
                  text={experts.length ? "No expert review requests are pending assignment." : "Create advocate or surveyor users before assigning reviews."}
                />
              )}
            </CardContent>
          </Card>

          <div className="mt-6 flex items-start gap-3 rounded-lg border bg-primary/5 p-4 text-sm leading-6 text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
            Admin workflows preserve the no-overclaim rule: official-source statuses remain visible and auditable.
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function EmptyInline({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
      <span className="text-primary">{icon}</span>
      {text}
    </div>
  );
}

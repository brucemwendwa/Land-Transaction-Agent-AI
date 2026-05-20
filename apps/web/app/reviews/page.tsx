"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { ArrowRight, Gavel, MapPinned } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingPanel } from "@/components/state-views";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface ReviewRequest {
  id: string;
  case_id: string;
  reviewer_role: string;
  reviewer_email: string;
  note: string;
  status: string;
  created_at: string;
}

export default function ReviewsPage() {
  const { getToken } = useAuth();
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const token = await getToken();
        setReviews(await apiFetch<ReviewRequest[]>("/reviews", token));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load reviews");
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  return (
    <AppShell>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Expert workflow</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Review requests</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Track advocate and surveyor review requests for transactions that need human judgment.
          </p>
        </div>
        <Badge variant="outline">{reviews.length} total</Badge>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading review requests" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} /></div> : null}
      {!loading && !error && !reviews.length ? (
        <div className="mt-6">
          <EmptyState title="No review requests yet" description="When a case needs advocate or surveyor input, the request will appear here with status and context." />
        </div>
      ) : null}

      {reviews.length ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          {reviews.map((review, index) => {
            const Icon = review.reviewer_role === "surveyor" ? MapPinned : Gavel;
            return (
              <motion.div
                key={review.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.035 }}
              >
                <Card className="premium-panel h-full">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle className="flex items-center gap-2 capitalize">
                        <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                        {review.reviewer_role} review
                      </CardTitle>
                      <StatusBadge tone={statusToneFromValue(review.status)} label={review.status.replaceAll("_", " ")} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm text-muted-foreground">
                    <div className="rounded-lg border bg-background/70 p-3">
                      <div className="font-medium text-foreground">{review.reviewer_email}</div>
                      <div className="mt-1 text-xs">{formatDate(review.created_at)}</div>
                    </div>
                    <p className="leading-6">{review.note || "No note provided."}</p>
                    <Button asChild variant="outline" className="w-full">
                      <Link href={`/cases/${review.case_id}/timeline`}>Open case timeline <ArrowRight className="h-4 w-4" /></Link>
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      ) : null}
    </AppShell>
  );
}

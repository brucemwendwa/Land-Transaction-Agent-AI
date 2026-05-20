"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAppAuth } from "@/lib/auth";
import { Activity, ArrowRight, CheckCircle2, Clock3, FileSearch, ShieldAlert } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingPanel } from "@/components/state-views";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface TimelineEvent {
  id: string;
  event_type: string;
  title: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export default function CaseTimelinePage() {
  const params = useParams<{ caseId: string }>();
  const { getToken } = useAppAuth();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const token = await getToken();
        setEvents(await apiFetch<TimelineEvent[]>(`/cases/${params.caseId}/timeline`, token));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load timeline");
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken, params.caseId]);

  return (
    <AppShell>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-primary">Transaction review</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Case timeline</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Follow each intake, upload, extraction, analysis, report, and review event in a chronological audit trail.
          </p>
        </div>
        <Button asChild variant="outline"><Link href={`/cases/${params.caseId}/analysis`}>Run analysis <ArrowRight className="h-4 w-4" /></Link></Button>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading transaction timeline" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} /></div> : null}
      {!loading && !error && !events.length ? (
        <div className="mt-6">
          <EmptyState
            title="No timeline events yet"
            description="Create a case, upload documents, run extraction, and request review to build a transaction audit trail."
            action={<Button asChild><Link href={`/cases/${params.caseId}/upload`}>Upload documents</Link></Button>}
          />
        </div>
      ) : null}

      {events.length ? (
        <div className="relative mt-8">
          <div className="absolute bottom-4 left-5 top-4 w-px bg-border" aria-hidden="true" />
          <div className="space-y-4">
            {events.map((event, index) => {
              const Icon = iconForEvent(event.event_type);
              return (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.035 }}
                  className="relative pl-12"
                >
                  <span className="absolute left-0 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full border bg-background shadow-sm">
                    <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                  </span>
                  <Card className="premium-panel">
                    <CardContent className="p-4 sm:p-5">
                      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div>
                          <div className="font-semibold">{event.title}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{formatDate(event.created_at)}</div>
                        </div>
                        <Badge variant="outline">{event.event_type.replaceAll("_", " ")}</Badge>
                      </div>
                      {Object.keys(event.metadata_json ?? {}).length ? (
                        <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                          {Object.entries(event.metadata_json).slice(0, 4).map(([key, value]) => (
                            <div key={key} className="rounded-md border bg-muted/40 p-2">
                              <span className="font-medium text-foreground">{key.replaceAll("_", " ")}:</span> {formatMeta(value)}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function iconForEvent(eventType: string) {
  if (eventType.includes("analysis") || eventType.includes("risk")) return ShieldAlert;
  if (eventType.includes("document") || eventType.includes("extract")) return FileSearch;
  if (eventType.includes("complete") || eventType.includes("report")) return CheckCircle2;
  if (eventType.includes("audit")) return Activity;
  return Clock3;
}

function formatMeta(value: unknown) {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

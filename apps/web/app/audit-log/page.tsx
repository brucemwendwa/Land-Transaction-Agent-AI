"use client";

import { useEffect, useState } from "react";
import { useAppAuth } from "@/lib/auth";
import { Activity, DatabaseZap, Fingerprint, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingPanel } from "@/components/state-views";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface AuditLog {
  id: string;
  actor_user_id: string | null;
  case_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  ip_address: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export default function AuditLogPage() {
  const { getToken } = useAppAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const token = await getToken();
        setLogs(await apiFetch<AuditLog[]>("/audit-logs", token));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load audit logs");
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  return (
    <AppShell>
      <div>
        <p className="text-sm font-medium text-primary">Security evidence</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Audit log</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Review user, case, document, report, and admin events recorded by the platform.
        </p>
      </div>

      {loading ? <div className="mt-6"><LoadingPanel label="Loading audit events" /></div> : null}
      {!loading && error ? <div className="mt-6"><ErrorState message={error} /></div> : null}
      {!loading && !error && !logs.length ? (
        <div className="mt-6">
          <EmptyState title="No audit events yet" description="Actions such as case creation, uploads, analysis, report generation, and review requests will appear here." />
        </div>
      ) : null}

      {logs.length ? (
        <div className="mt-6 space-y-3">
          {logs.map((log, index) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.025 }}
            >
              <Card className="premium-panel">
                <CardContent className="grid gap-4 p-4 md:grid-cols-[1fr_auto] md:items-center">
                  <div className="flex min-w-0 gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border bg-muted">
                      {iconForAction(log.action)}
                    </span>
                    <div className="min-w-0">
                      <div className="truncate font-semibold">{log.action.replaceAll(".", " ")}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatDate(log.created_at)} · {log.ip_address || "no ip recorded"}</div>
                      <div className="mt-1 truncate text-xs text-muted-foreground">Actor: {log.actor_user_id ?? "system"}</div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 md:justify-end">
                    <Badge variant="outline">{log.target_type}</Badge>
                    <Badge variant="secondary">{log.target_id.slice(0, 8)}</Badge>
                    {log.case_id ? <Badge variant="info">case {log.case_id.slice(0, 8)}</Badge> : null}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : null}
    </AppShell>
  );
}

function iconForAction(action: string) {
  if (action.includes("document") || action.includes("upload")) return <DatabaseZap className="h-5 w-5 text-primary" aria-hidden="true" />;
  if (action.includes("auth") || action.includes("user")) return <Fingerprint className="h-5 w-5 text-primary" aria-hidden="true" />;
  if (action.includes("report") || action.includes("analysis")) return <ShieldCheck className="h-5 w-5 text-primary" aria-hidden="true" />;
  return <Activity className="h-5 w-5 text-primary" aria-hidden="true" />;
}

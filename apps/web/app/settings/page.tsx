"use client";

import { UserProfile } from "@clerk/nextjs";
import { KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <AppShell>
      <div>
        <p className="text-sm font-medium text-primary">Account controls</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Manage your profile while the platform keeps security, audit, and verification boundaries visible.
        </p>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="overflow-hidden rounded-lg border bg-card p-2 shadow-sm">
          <UserProfile />
        </div>
        <aside className="space-y-4">
          <Card className="premium-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" aria-hidden="true" />
                Security posture
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>Production uses Clerk JWTs, backend RBAC, signed URLs, malware checks, rate limiting, and audit logs.</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="success">JWT auth</Badge>
                <Badge variant="info">Signed URLs</Badge>
                <Badge variant="outline">Audit logs</Badge>
              </div>
            </CardContent>
          </Card>
          <Card className="premium-panel">
            <CardContent className="flex gap-3 p-4">
              <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="text-sm leading-6 text-muted-foreground">
                Official ownership claims remain disabled unless an official adapter returns verified evidence.
              </p>
            </CardContent>
          </Card>
          <Card className="premium-panel">
            <CardContent className="flex gap-3 p-4">
              <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="text-sm leading-6 text-muted-foreground">
                Use strong account authentication and invite reviewers only when you trust the recipient email.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </AppShell>
  );
}

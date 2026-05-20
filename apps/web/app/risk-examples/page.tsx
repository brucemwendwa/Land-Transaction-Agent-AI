"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, SearchCheck } from "lucide-react";
import { motion } from "framer-motion";
import { PublicHeader } from "@/components/public-header";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const examples = [
  { title: "Parcel number mismatch", body: "The title deed says LR 209/1234 while the sale agreement says LR 209/1234/2.", severity: "High", score: 74 },
  { title: "Stale official search", body: "A search certificate is older than 30 days, so new cautions or charges may not be reflected.", severity: "Medium", score: 48 },
  { title: "Gazette conflict", body: "A Gazette notice references loss, rectification, restriction, or revocation for a related parcel.", severity: "High", score: 78 },
  { title: "Payment before verification", body: "The buyer has released funds before official and professional checks are complete.", severity: "Critical", score: 91 }
];

export default function RiskExamplesPage() {
  return (
    <main className="min-h-screen">
      <PublicHeader />
      <section className="border-b bg-muted/40 py-16">
        <div className="section-shell">
          <Badge variant="secondary">Risk engine examples</Badge>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight sm:text-5xl">Risk Examples</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base">
            These examples show how the system explains risk without pretending to verify ownership unless official evidence is available.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Button asChild><Link href="/cases/new">Start Land Risk Check <ArrowRight className="h-4 w-4" /></Link></Button>
            <Button asChild variant="outline"><Link href="/">Back home</Link></Button>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="section-shell">
          <div className="grid gap-4 md:grid-cols-2">
            {examples.map((example, index) => (
              <motion.div
                key={example.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                <Card className="premium-panel h-full">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <CardTitle className="flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden="true" />
                        {example.title}
                      </CardTitle>
                      <StatusBadge tone={example.severity === "Critical" || example.severity === "High" ? "high_risk" : "needs_review"} label={example.severity} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <p className="text-sm leading-6 text-muted-foreground">{example.body}</p>
                    <RiskMeter score={example.score} band={example.severity.toLowerCase()} />
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="flex items-start gap-3 rounded-lg border bg-emerald-500/10 p-5 text-sm leading-6 text-emerald-800 dark:text-emerald-200">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              Every report includes evidence, status, and next steps so a buyer knows whether to pause, request a fresh search, or ask for professional review.
            </div>
            <div className="flex items-start gap-3 rounded-lg border bg-primary/5 p-5 text-sm leading-6 text-muted-foreground">
              <SearchCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              Official-source status is shown separately from AI extraction confidence to avoid misleading the buyer.
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, BookOpenCheck, Clock3, FileSearch, Fingerprint, Gavel, Landmark, ShieldAlert, UsersRound } from "lucide-react";
import { motion } from "framer-motion";
import { PublicHeader } from "@/components/public-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const fraudPatterns = [
  {
    title: "Fake seller",
    icon: Fingerprint,
    severity: "critical",
    detectedBy: "Seller name, ID, KRA PIN, signatures, and search-certificate owner comparison.",
    buyerMove: "Pause payment and ask an advocate to confirm the seller's authority and identity."
  },
  {
    title: "Duplicate title",
    icon: FileSearch,
    severity: "critical",
    detectedBy: "Repeated parcel/title references, inconsistent title numbers, and duplicate parcel signals across cases.",
    buyerMove: "Insist on a fresh official search and professional title inspection before signing."
  },
  {
    title: "Old search certificate",
    icon: Clock3,
    severity: "high",
    detectedBy: "Search-certificate issue date older than 30 days.",
    buyerMove: "Request a fresh search certificate before paying a deposit."
  },
  {
    title: "Missing consent",
    icon: Gavel,
    severity: "high",
    detectedBy: "Missing consent to transfer or spousal consent in the due-diligence checklist.",
    buyerMove: "Confirm consent requirements and collect signed consent before completion."
  },
  {
    title: "Multiple owners but one signer",
    icon: UsersRound,
    severity: "high",
    detectedBy: "Owner names from title/search evidence compared with seller signatures and agreement parties.",
    buyerMove: "Require all owners to sign or produce properly verified authority."
  },
  {
    title: "Land under caution, restriction, or charge",
    icon: ShieldAlert,
    severity: "critical",
    detectedBy: "Encumbrance, caution, restriction, charge, or dispute terms extracted from the search certificate.",
    buyerMove: "Resolve the encumbrance or restriction with counsel before funds move."
  },
  {
    title: "Altered documents",
    icon: AlertTriangle,
    severity: "critical",
    detectedBy: "Poor image quality, overwritten text, inconsistent font, missing seal, or visual suspicion signals.",
    buyerMove: "Ask for original documents and manual professional inspection."
  },
  {
    title: "Suspicious payment pressure",
    icon: Landmark,
    severity: "high",
    detectedBy: "Payment-before-verification flag or critical-risk report state.",
    buyerMove: "Do not release funds until official and professional checks are complete."
  },
  {
    title: "Power of attorney misuse",
    icon: BookOpenCheck,
    severity: "critical",
    detectedBy: "Power of attorney uploaded without key date, identity, signature, seal, or authority evidence.",
    buyerMove: "Verify the power of attorney with an advocate and relevant registry."
  }
];

const principles = [
  "AI extraction is evidence, not ownership proof.",
  "A Gazette no-match is not official registry verification.",
  "Every serious warning should point to the document and value that caused it.",
  "Fresh official search evidence and human experts still matter before payment."
];

export default function RiskExamplesPage() {
  return (
    <main className="min-h-screen">
      <PublicHeader />
      <section className="border-b bg-muted/40 py-16">
        <div className="section-shell">
          <Badge variant="secondary">Fraud pattern library</Badge>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight sm:text-5xl">Common Kenyan Land Fraud Risks</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base">
            Learn what Mradi wa Ardhi looks for when it reviews uploaded land transaction evidence. The system explains risk signals without claiming official ownership verification unless official evidence exists.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Button asChild><Link href="/cases/new">Start Land Risk Check <ArrowRight className="h-4 w-4" /></Link></Button>
            <Button asChild variant="outline"><Link href="/">Back home</Link></Button>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="section-shell grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {fraudPatterns.map((pattern, index) => {
            const Icon = pattern.icon;
            return (
              <motion.article
                key={pattern.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.035 }}
              >
                <Card className="premium-panel h-full">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                        <CardTitle className="mt-3">{pattern.title}</CardTitle>
                      </div>
                      <StatusBadge tone={pattern.severity === "critical" ? "high_risk" : "needs_review"} label={pattern.severity} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Detected through</div>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">{pattern.detectedBy}</p>
                    </div>
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Buyer move</div>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">{pattern.buyerMove}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.article>
            );
          })}
        </div>
      </section>

      <section className="border-y bg-muted/40 py-16">
        <div className="section-shell grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
          <div>
            <p className="text-sm font-medium text-primary">Trust principles</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Competition-ready means explainable, careful, and honest.</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {principles.map((principle) => (
              <div key={principle} className="rounded-lg border bg-background p-4 text-sm leading-6 text-muted-foreground">
                {principle}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

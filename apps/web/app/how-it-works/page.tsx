"use client";

import Link from "next/link";
import { ArrowRight, FileUp, ScanSearch, ShieldCheck, Users } from "lucide-react";
import { motion } from "framer-motion";
import { PublicHeader } from "@/components/public-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const steps = [
  { title: "Create a case", body: "Record buyer, seller, parcel number, county, and payment timing.", icon: FileUp },
  { title: "Upload documents", body: "Use signed upload URLs and malware scanning before files become analysable.", icon: FileUp },
  { title: "Review extraction", body: "Confirm AI/OCR extracted parcel, owner, ID, dates, registry, and document signals.", icon: ScanSearch },
  { title: "Run risk analysis", body: "Specialized agents compare evidence, public Gazette mentions, uploaded search certificates, and deterministic risk rules.", icon: ShieldCheck },
  { title: "Request review", body: "Invite an advocate or surveyor when risk or missing verification requires professional review.", icon: Users }
];

export default function HowItWorksPage() {
  return (
    <main className="min-h-screen">
      <PublicHeader />
      <section className="border-b bg-muted/40 py-16">
        <div className="section-shell">
          <Badge variant="secondary">Evidence-first diligence</Badge>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight sm:text-5xl">How Mradi wa Ardhi Works</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base">
            The workflow separates observed evidence from professional or official verification, so buyers can see what is known and what still needs confirmation.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Button asChild><Link href="/cases/new">Create your first case <ArrowRight className="h-4 w-4" /></Link></Button>
            <Button asChild variant="outline"><Link href="/">Back home</Link></Button>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="section-shell">
          <div className="grid gap-4 md:grid-cols-2">
            {steps.map(({ title, body, icon: Icon }, index) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04 }}
              >
                <Card className="premium-panel h-full">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">{index + 1}</span>
                      <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                      <CardTitle>{title}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="text-sm leading-6 text-muted-foreground">{body}</CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
          <div className="mt-6 rounded-lg border bg-primary/5 p-5 text-sm leading-6 text-muted-foreground">
            Official ownership verification is never implied. If the system only parsed uploaded evidence, the report says so clearly.
          </div>
        </div>
      </section>
    </main>
  );
}

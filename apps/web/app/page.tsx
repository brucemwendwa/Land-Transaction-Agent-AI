"use client";

import Link from "next/link";
import { useState } from "react";
import { SignedIn, SignedOut, SignInButton, SignUpButton, useAuth } from "@clerk/nextjs";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  CheckCircle2,
  FileSearch,
  Fingerprint,
  Gavel,
  Landmark,
  LockKeyhole,
  MapPinned,
  Scale,
  ShieldCheck,
  ShieldQuestion,
  UserRoundCheck
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ModeToggle } from "@/components/mode-toggle";
import { RiskMeter } from "@/components/risk-meter";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api";

const trustCards = [
  { title: "Document intelligence", body: "OCR and vision extraction for titles, IDs, agreements, maps, and consents.", icon: FileSearch },
  { title: "Gazette cross-checking", body: "Public Kenya Gazette mentions are surfaced as evidence, not overclaimed as registry verification.", icon: BookOpenCheck },
  { title: "Parcel consistency checks", body: "Parcel, registry, block, plot, owner, seller, ID, and date signals are compared across files.", icon: MapPinned },
  { title: "Buyer-friendly risk report", body: "Plain-English risk factors, evidence, next steps, and downloadable PDF reporting.", icon: Scale },
  { title: "Human expert review ready", body: "Escalate high-risk or uncertain cases to an advocate or surveyor review workflow.", icon: UserRoundCheck }
];

const documents = [
  "Title deed",
  "Sale agreement",
  "National ID or passport",
  "KRA PIN certificate",
  "Land search certificate",
  "Mutation form",
  "Survey map",
  "Consent to transfer",
  "Rates clearance",
  "Land rent clearance",
  "Spousal consent",
  "Power of attorney",
  "Kenya Gazette notice",
  "Other supporting documents"
];

const riskExamples = [
  { score: 22, band: "Low", title: "Fresh search, matching parties", tone: "verified" as const },
  { score: 48, band: "Medium", title: "Missing rent or rates clearance", tone: "needs_review" as const },
  { score: 74, band: "High", title: "Seller and parcel mismatch", tone: "high_risk" as const },
  { score: 91, band: "Critical", title: "Payment before verification", tone: "high_risk" as const }
];

const pricingPlans = [
  { name: "Buyer", price: "KES 2,500", body: "Single transaction risk check with PDF report and clear next steps.", featured: false },
  { name: "Professional", price: "KES 12,000", body: "For advocates, surveyors, agents, and repeat buyers managing several files.", featured: true },
  { name: "Institution", price: "Custom", body: "For banks, SACCOs, and diligence teams needing audit-ready workflows.", featured: false }
];

const reportPreviewItems = [
  { title: "Parcel consistency", body: "Mismatch between title and sale agreement", icon: ShieldQuestion },
  { title: "Official search", body: "Uploaded certificate parsed, not independently verified", icon: BadgeCheck }
];

const faqs = [
  ["Does this replace an advocate?", "No. It prepares the transaction for safer professional review and clearly states when official verification has not happened."],
  ["Can it verify ownership from Ardhisasa?", "Only when an official integration or uploaded official search certificate is available. Otherwise the status remains not verified from official source."],
  ["What documents should I start with?", "Begin with the title deed, official search certificate, sale agreement, seller ID or passport, KRA PIN, consents, maps, rates, and rent clearance."],
  ["Can banks, SACCOs, or firms use it?", "Yes. The workflow, audit logs, and review-ready reports are designed for professional diligence teams as well as individual buyers."]
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden">
      <header className="absolute left-0 right-0 top-0 z-20">
        <div className="section-shell flex items-center justify-between py-4 text-white">
          <Link href="/" className="focus-ring flex items-center gap-3 rounded-md font-semibold">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/20 backdrop-blur">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            Mradi wa Ardhi
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-white/80 md:flex" aria-label="Landing navigation">
            <a className="hover:text-white" href="#problem">Fraud problem</a>
            <a className="hover:text-white" href="#how">How it works</a>
            <a className="hover:text-white" href="#report">Report preview</a>
            <a className="hover:text-white" href="#faq">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            <ModeToggle />
            <SignedOut>
              <SignInButton mode="modal">
                <Button variant="secondary" size="sm">Login</Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Button asChild size="sm">
                <Link href="/dashboard">Dashboard</Link>
              </Button>
            </SignedIn>
          </div>
        </div>
      </header>

      <section className="hero-photo relative min-h-[94vh]">
        <div className="section-shell flex min-h-[94vh] items-center pb-20 pt-28">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: "easeOut" }}
            className="max-w-4xl text-white"
          >
            <Badge className="mb-5 bg-white/20 text-white backdrop-blur">Premium AI due diligence for Kenyan land buyers</Badge>
            <h1 className="max-w-4xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
              Before You Buy Land, Let AI Stress-Test the Deal.
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-8 text-white/80 sm:text-lg">
              Upload title deeds, search certificates, sale agreements, maps, and consent documents. Mradi wa Ardhi checks inconsistencies, missing documents, suspicious dates, and Gazette-related risks before you sign.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <SignedOut>
                <SignUpButton mode="modal">
                  <Button size="lg">Start Land Risk Check <ArrowRight className="h-4 w-4" /></Button>
                </SignUpButton>
              </SignedOut>
              <SignedIn>
                <Button asChild size="lg"><Link href="/cases/new">Start Land Risk Check</Link></Button>
              </SignedIn>
              <Button asChild variant="secondary" size="lg">
                <a href="#how">See How It Works</a>
              </Button>
            </div>
            <div className="mt-10 grid max-w-3xl gap-3 text-sm text-white/80 sm:grid-cols-3">
              {["No ownership overclaims", "Audit-ready workflow", "Advocate review ready"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
                  {item}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      <section className="border-b bg-background py-12">
        <div className="section-shell grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {trustCards.map((card, index) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ delay: index * 0.04 }}
              >
                <Card className="premium-panel h-full">
                  <CardHeader>
                    <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                    <CardTitle className="text-base">{card.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm leading-6 text-muted-foreground">{card.body}</CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </section>

      <section id="problem" className="py-20">
        <div className="section-shell grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-sm font-medium text-primary">The fraud problem</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Land fraud hides in small document contradictions.</h2>
            <p className="mt-4 leading-7 text-muted-foreground">
              Forged titles, stale searches, altered IDs, backdated agreements, missing consents, and boundary inconsistencies can be expensive to discover after funds move.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Parcel mismatch", "Different LR, block, section, or plot numbers across documents."],
              ["Suspicious dates", "Sale agreement appears before search or certificate is older than 30 days."],
              ["Missing consents", "Transfer, spousal, POA, rent, or rates documents are absent."],
              ["Not officially verified", "Uploaded evidence is parsed without pretending registry access happened."]
            ].map(([title, body]) => (
              <Card key={title} className="premium-panel">
                <CardContent className="p-5">
                  <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden="true" />
                  <h3 className="mt-3 font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="border-y bg-muted/40 py-20">
        <div className="section-shell">
          <div className="max-w-3xl">
            <p className="text-sm font-medium text-primary">How the agent works</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">From uploaded evidence to buyer-ready risk report.</h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-4">
            {[
              { icon: LockKeyhole, title: "Secure intake", body: "Create a case and upload documents with signed URLs." },
              { icon: Fingerprint, title: "Document extraction", body: "Extract names, IDs, parcel numbers, dates, registry, section, block, and plot." },
              { icon: Landmark, title: "Cross-checks", body: "Compare files and search public Gazette evidence where available." },
              { icon: Gavel, title: "Risk report", body: "Generate a plain-English report and route uncertain cases to experts." }
            ].map((step, index) => {
              const Icon = step.icon;
              return (
                <Card key={step.title} className="premium-panel">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                      <span className="text-xs text-muted-foreground">0{index + 1}</span>
                    </div>
                    <CardTitle>{step.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm leading-6 text-muted-foreground">{step.body}</CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="section-shell grid gap-10 lg:grid-cols-[0.85fr_1.15fr]">
          <div>
            <p className="text-sm font-medium text-primary">Documents checked</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Built for the full diligence packet.</h2>
            <p className="mt-4 leading-7 text-muted-foreground">
              Upload core transaction files first, then add supporting records for stronger comparison and review readiness.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {documents.map((document) => <Badge key={document} variant="secondary">{document}</Badge>)}
          </div>
        </div>
      </section>

      <section className="border-y bg-muted/40 py-20">
        <div className="section-shell">
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-medium text-primary">Risk score examples</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Simple score. Evidence-backed explanation.</h2>
            </div>
            <Button asChild variant="outline"><Link href="/risk-examples">Explore examples</Link></Button>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {riskExamples.map((risk) => (
              <Card key={risk.title} className="premium-panel">
                <CardContent className="space-y-4 p-5">
                  <StatusBadge tone={risk.tone} label={risk.band} />
                  <div className="text-3xl font-semibold">{risk.score}/100</div>
                  <p className="text-sm leading-6 text-muted-foreground">{risk.title}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="report" className="py-20">
        <div className="section-shell grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-sm font-medium text-primary">Report preview</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">A report a buyer can understand and an expert can review.</h2>
            <p className="mt-4 leading-7 text-muted-foreground">
              Every risk includes a clear reason, supporting evidence, and a recommended next step. Official-source uncertainty is visible by design.
            </p>
          </div>
          <Card className="premium-panel">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle>Land Risk Report: Kitengela Parcel</CardTitle>
                <StatusBadge tone="needs_review" label="Needs expert review" />
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <RiskMeter score={68} band="high" />
              <div className="grid gap-3 sm:grid-cols-2">
                {reportPreviewItems.map(({ title, body, icon: Icon }) => (
                  <div key={title} className="rounded-lg border bg-background p-4">
                    <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                    <h3 className="mt-3 font-medium">{title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{body}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="border-y bg-muted/40 py-20">
        <div className="section-shell">
          <div className="max-w-3xl">
            <p className="text-sm font-medium text-primary">Pricing preview</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Start with one deal. Scale to a diligence desk.</h2>
            <p className="mt-4 leading-7 text-muted-foreground">
              Plan selection is saved to your account for follow-up. Payment processing can be connected without changing the diligence workflow.
            </p>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {pricingPlans.map((plan) => (
              <Card key={plan.name} className={`premium-panel ${plan.featured ? "border-primary" : ""}`}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle>{plan.name}</CardTitle>
                    {plan.featured ? <Badge variant="success">Popular</Badge> : null}
                  </div>
                  <div className="pt-2 text-3xl font-semibold">{plan.price}</div>
                </CardHeader>
                <CardContent className="space-y-5">
                  <p className="text-sm leading-6 text-muted-foreground">{plan.body}</p>
                  <PricingPlanButton plan={plan.name.toLowerCase()} featured={plan.featured} />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="faq" className="border-y bg-muted/40 py-20">
        <div className="section-shell">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-primary">FAQ</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Built for trust before speed.</h2>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {faqs.map(([question, answer]) => (
              <Card key={question} className="premium-panel">
                <CardHeader><CardTitle className="text-lg">{question}</CardTitle></CardHeader>
                <CardContent className="text-sm leading-6 text-muted-foreground">{answer}</CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-primary py-16 text-primary-foreground">
        <div className="section-shell">
          <p className="text-sm font-medium text-primary-foreground/70">Legal disclaimer</p>
          <h2 className="mt-2 text-3xl font-semibold">AI assistance, not legal advice or official registry verification.</h2>
          <p className="mt-4 max-w-4xl leading-7 text-primary-foreground/80">
            Mradi wa Ardhi does not replace an advocate, surveyor, valuer, bank diligence team, SACCO process, or official land registry search. If an official API is unavailable, the system clearly reports that status and routes the case to uploaded-certificate parsing or manual verification.
          </p>
        </div>
      </section>

      <footer className="border-t py-8">
        <div className="section-shell flex flex-col justify-between gap-4 text-sm text-muted-foreground sm:flex-row">
          <span>© 2026 Mradi wa Ardhi</span>
          <span>Premium land diligence for buyers, advocates, surveyors, banks, and SACCOs.</span>
        </div>
      </footer>
    </main>
  );
}

function PricingPlanButton({ plan, featured }: { plan: string; featured: boolean }) {
  const { getToken, isSignedIn } = useAuth();
  const [status, setStatus] = useState("");

  async function selectPlan() {
    if (!isSignedIn) {
      window.location.href = "/sign-up";
      return;
    }
    const token = await getToken();
    await apiFetch("/pricing/selection", token, {
      method: "POST",
      body: JSON.stringify({ plan_key: plan })
    });
    setStatus("Selected");
  }

  return (
    <div className="space-y-2">
      <Button variant={featured ? "default" : "outline"} className="w-full" onClick={selectPlan}>
        Select {plan}
      </Button>
      {status ? <p className="text-center text-xs text-muted-foreground">{status}</p> : null}
    </div>
  );
}

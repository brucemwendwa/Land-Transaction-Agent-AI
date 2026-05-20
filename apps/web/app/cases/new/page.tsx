"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { ArrowRight, CheckCircle2, FileText, Landmark, LockKeyhole, MapPinned } from "lucide-react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { ProgressTracker } from "@/components/progress-tracker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { apiFetch, type ApiCase } from "@/lib/api";

export default function NewCasePage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const token = await getToken();
      const landCase = await apiFetch<ApiCase>("/cases", token, {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          buyer_name: form.get("buyer_name"),
          seller_name: form.get("seller_name"),
          parcel_number_claimed: form.get("parcel_number_claimed"),
          location_county: form.get("location_county"),
          preferred_language: form.get("preferred_language"),
          payment_before_verification: form.get("payment_before_verification") === "on"
        })
      });
      router.push(`/cases/${landCase.id}/upload`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create case");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <ProgressTracker current="case" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28 }}>
          <div className="mb-6">
            <p className="text-sm font-medium text-primary">New transaction case</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Create case</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Capture the buyer, seller, parcel, county, and payment posture before uploading evidence.
            </p>
          </div>
          <Card className="premium-panel">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" aria-hidden="true" />
                Transaction basics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <Label htmlFor="title">Case title</Label>
                  <Input id="title" name="title" required placeholder="Kitengela parcel purchase" />
                </div>
                <div>
                  <Label htmlFor="buyer_name">Buyer name</Label>
                  <Input id="buyer_name" name="buyer_name" placeholder="Jane Wanjiku" />
                </div>
                <div>
                  <Label htmlFor="seller_name">Seller name</Label>
                  <Input id="seller_name" name="seller_name" placeholder="John Mwangi" />
                </div>
                <div>
                  <Label htmlFor="parcel_number_claimed">Claimed parcel number</Label>
                  <Input id="parcel_number_claimed" name="parcel_number_claimed" placeholder="LR 209/..." />
                </div>
                <div>
                  <Label htmlFor="location_county">County</Label>
                  <Input id="location_county" name="location_county" placeholder="Kajiado" />
                </div>
                <div>
                  <Label htmlFor="preferred_language">Report language</Label>
                  <Select id="preferred_language" name="preferred_language" defaultValue="en">
                    <option value="en">English</option>
                    <option value="sw">English with Kiswahili summary</option>
                  </Select>
                </div>
                <label className="flex min-h-10 items-start gap-3 rounded-md border bg-muted/40 p-3 text-sm md:mt-6">
                  <input className="mt-1 h-4 w-4 accent-primary" type="checkbox" name="payment_before_verification" />
                  <span>Buyer may pay before verification is complete</span>
                </label>
                {error ? (
                  <div className="md:col-span-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                    {error}
                  </div>
                ) : null}
                <div className="md:col-span-2">
                  <Button disabled={loading} className="w-full sm:w-auto">
                    {loading ? "Creating..." : "Create and upload documents"}
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:h-fit">
          {[
            { icon: MapPinned, title: "Parcel first", body: "Add the claimed parcel number if available so later extraction can compare it." },
            { icon: Landmark, title: "County context", body: "County and registry details help reviewers understand rates, rent, and land office context." },
            { icon: LockKeyhole, title: "Payment posture", body: "Mark payment-before-verification honestly. It affects the risk score and next steps." }
          ].map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.title} className="premium-panel">
                <CardContent className="flex gap-3 p-4">
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                  <div>
                    <div className="font-medium">{item.title}</div>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.body}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
          <div className="flex items-start gap-2 rounded-lg border bg-emerald-500/10 p-4 text-sm text-emerald-800 dark:text-emerald-200">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            Cases are private to authorized users and every action is audit logged.
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

import Link from "next/link";
import { ArrowLeft, Scale } from "lucide-react";
import { PublicHeader } from "@/components/public-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LEGAL_DISCLAIMER } from "@/lib/legal";

interface LegalPageProps {
  eyebrow: string;
  title: string;
  sections: ReadonlyArray<{ title: string; body: string }>;
}

export function LegalPage({ eyebrow, title, sections }: LegalPageProps) {
  return (
    <main className="min-h-screen">
      <PublicHeader />
      <section className="border-b bg-muted/40 py-14">
        <div className="section-shell">
          <Button asChild variant="ghost" className="mb-5 px-0 hover:bg-transparent">
            <Link href="/"><ArrowLeft className="h-4 w-4" /> Back home</Link>
          </Button>
          <Badge variant="secondary">{eyebrow}</Badge>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base">
            {LEGAL_DISCLAIMER}
          </p>
        </div>
      </section>
      <section className="py-14">
        <div className="section-shell grid gap-4 md:grid-cols-2">
          {sections.map((section) => (
            <Card key={section.title} className="premium-panel">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Scale className="h-5 w-5 text-primary" aria-hidden="true" />
                  {section.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-muted-foreground">{section.body}</CardContent>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}

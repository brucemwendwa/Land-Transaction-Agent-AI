"use client";

import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { ModeToggle } from "@/components/mode-toggle";
import { Button } from "@/components/ui/button";

export function PublicHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur-xl">
      <div className="section-shell flex items-center justify-between py-3">
        <Link href="/" className="focus-ring flex items-center gap-3 rounded-md font-semibold">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>
            <span className="block leading-none">Mradi wa Ardhi</span>
            <span className="hidden text-xs font-normal text-muted-foreground sm:block">Land Transaction Agent</span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <ModeToggle />
          <Button asChild variant="outline" size="sm"><Link href="/sign-in">Login</Link></Button>
          <Button asChild size="sm"><Link href="/dashboard">Dashboard</Link></Button>
        </div>
      </div>
    </header>
  );
}

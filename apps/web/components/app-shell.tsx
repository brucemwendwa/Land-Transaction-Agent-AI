"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, FileText, Home, LayoutDashboard, ScrollText, Settings, ShieldCheck, UserRoundCheck } from "lucide-react";
import { motion } from "framer-motion";
import { ModeToggle } from "@/components/mode-toggle";
import { cn } from "@/lib/utils";
import { AuthUserButton } from "@/lib/auth";
import { LEGAL_DISCLAIMER, legalLinks } from "@/lib/legal";

const links = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cases/new", label: "New case", icon: FileText },
  { href: "/reviews", label: "Reviews", icon: ShieldCheck },
  { href: "/expert", label: "Expert", icon: UserRoundCheck },
  { href: "/admin", label: "Admin", icon: LayoutDashboard },
  { href: "/audit-log", label: "Audit", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="focus-ring flex items-center gap-3 rounded-md font-semibold">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <ScrollText className="h-4 w-4" aria-hidden="true" />
            </span>
            <span>
              <span className="block leading-none">Mradi wa Ardhi</span>
              <span className="hidden text-xs font-normal text-muted-foreground sm:block">Land Transaction Agent</span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <ModeToggle />
            <AuthUserButton />
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-5 sm:px-6 md:grid-cols-[238px_1fr] lg:px-8">
        <nav aria-label="Primary navigation" className="flex gap-2 overflow-auto pb-1 md:sticky md:top-20 md:block md:h-[calc(100vh-6rem)] md:space-y-2 md:overflow-visible md:pb-0">
          {links.map((link) => {
            const Icon = link.icon;
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "focus-ring relative flex min-w-fit items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="min-w-0">
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            {children}
          </motion.main>
          <footer className="mt-10 border-t py-5 text-xs leading-5 text-muted-foreground">
            <p>{LEGAL_DISCLAIMER}</p>
            <div className="mt-3 flex flex-wrap gap-3">
              {legalLinks.map((link) => (
                <Link key={link.href} href={link.href} className="font-medium text-foreground hover:text-primary">
                  {link.label}
                </Link>
              ))}
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}

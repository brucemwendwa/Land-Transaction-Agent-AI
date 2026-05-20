"use client";

import { SignIn, SignUp, useAuth as useClerkAuth, UserButton, UserProfile } from "@clerk/nextjs";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const placeholderClerkKey = "pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk";

export const isClerkConfigured =
  Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) &&
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY !== placeholderClerkKey;

type AppAuth = {
  getToken: () => Promise<string | null>;
  isSignedIn?: boolean;
};

function useDevelopmentAuth(): AppAuth {
  return {
    getToken: async () => null,
    isSignedIn: true
  };
}

export const useAppAuth: () => AppAuth = isClerkConfigured ? useClerkAuth : useDevelopmentAuth;

export function AuthUserButton() {
  if (!isClerkConfigured) {
    return (
      <span className="rounded-md border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
        Dev auth
      </span>
    );
  }
  return <UserButton />;
}

export function AuthSignIn() {
  if (isClerkConfigured) return <SignIn />;
  return <DevelopmentAuthPanel mode="sign-in" />;
}

export function AuthSignUp() {
  if (isClerkConfigured) return <SignUp />;
  return <DevelopmentAuthPanel mode="sign-up" />;
}

export function AuthUserProfile() {
  if (isClerkConfigured) return <UserProfile />;
  return (
    <div className="p-6">
      <h2 className="font-semibold">Local development profile</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Clerk profile management appears here when a real Clerk publishable key is configured.
      </p>
    </div>
  );
}

function DevelopmentAuthPanel({ mode }: { mode: "sign-in" | "sign-up" }) {
  return (
    <div className="mx-auto max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
      <h1 className="text-xl font-semibold">Development authentication is enabled</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        This workspace is using the local auth bypass. Configure a real Clerk publishable key to use the hosted {mode} flow.
      </p>
      <Button asChild className="mt-5">
        <Link href="/dashboard">Continue to dashboard</Link>
      </Button>
    </div>
  );
}

"use client";

import { SignedIn, SignedOut, SignIn, SignUp, useAuth as useClerkAuth, UserButton, UserProfile } from "@clerk/nextjs";
import Link from "next/link";
import { Button, type ButtonProps } from "@/components/ui/button";
import { PLACEHOLDER_CLERK_PUBLISHABLE_KEY, type AuthConfigurationIssue } from "@/lib/auth-config";
import { AUTH_REDIRECT_PATH } from "@/lib/auth-routes";

const isProduction = process.env.NODE_ENV === "production";

export const isClerkConfigured =
  Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) &&
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY !== PLACEHOLDER_CLERK_PUBLISHABLE_KEY;

export const canUseDevelopmentAuth = !isProduction && !isClerkConfigured;

type AppAuth = {
  getToken: () => Promise<string | null>;
  isSignedIn?: boolean;
};

const developmentAuth: AppAuth = {
  getToken: async () => null,
  isSignedIn: true
};

function useDevelopmentAuth(): AppAuth {
  return developmentAuth;
}

const missingProductionAuth: AppAuth = {
  getToken: async () => {
    throw new Error("Authentication is not configured for production");
  },
  isSignedIn: false
};

function useMissingProductionAuth(): AppAuth {
  return missingProductionAuth;
}

export const useAppAuth: () => AppAuth = isClerkConfigured
  ? useClerkAuth
  : canUseDevelopmentAuth
    ? useDevelopmentAuth
    : useMissingProductionAuth;

export function AuthUserButton() {
  if (!isClerkConfigured) {
    if (isProduction) return <AuthConfigurationError compact />;
    return (
      <span className="rounded-md border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
        Dev auth
      </span>
    );
  }
  return <UserButton />;
}

export function PublicAuthActions({
  loginVariant = "outline",
  dashboardVariant = "default"
}: {
  loginVariant?: ButtonProps["variant"];
  dashboardVariant?: ButtonProps["variant"];
}) {
  if (!isClerkConfigured) {
    return (
      <>
        <Button asChild variant={loginVariant} size="sm"><Link href="/sign-in">Login</Link></Button>
        <Button asChild variant={dashboardVariant} size="sm"><Link href={AUTH_REDIRECT_PATH}>Dashboard</Link></Button>
      </>
    );
  }

  return (
    <>
      <SignedOut>
        <Button asChild variant={loginVariant} size="sm"><Link href="/sign-in">Login</Link></Button>
        <Button asChild variant={dashboardVariant} size="sm"><Link href={AUTH_REDIRECT_PATH}>Dashboard</Link></Button>
      </SignedOut>
      <SignedIn>
        <Button asChild variant={dashboardVariant} size="sm"><Link href={AUTH_REDIRECT_PATH}>Dashboard</Link></Button>
        <UserButton />
      </SignedIn>
    </>
  );
}

export function AuthSignIn() {
  if (isClerkConfigured) {
    return <SignIn fallbackRedirectUrl={AUTH_REDIRECT_PATH} signUpFallbackRedirectUrl={AUTH_REDIRECT_PATH} />;
  }
  if (isProduction) return <AuthConfigurationError />;
  return <DevelopmentAuthPanel mode="sign-in" />;
}

export function AuthSignUp() {
  if (isClerkConfigured) {
    return <SignUp fallbackRedirectUrl={AUTH_REDIRECT_PATH} signInFallbackRedirectUrl={AUTH_REDIRECT_PATH} />;
  }
  if (isProduction) return <AuthConfigurationError />;
  return <DevelopmentAuthPanel mode="sign-up" />;
}

export function AuthUserProfile() {
  if (isClerkConfigured) {
    return (
      <UserProfile
        routing="hash"
        appearance={{
          elements: {
            rootBox: "w-full",
            cardBox: "w-full max-w-none shadow-none"
          }
        }}
      />
    );
  }
  if (isProduction) return <AuthConfigurationError />;
  return (
    <div className="p-6">
      <h2 className="font-semibold">Local development profile</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Clerk profile management appears here when a real Clerk publishable key is configured.
      </p>
    </div>
  );
}

export function AuthConfigurationError({
  compact = false,
  issues = []
}: {
  compact?: boolean;
  issues?: AuthConfigurationIssue[];
}) {
  if (compact) {
    return (
      <span className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-1 text-xs font-medium text-destructive">
        Auth not configured
      </span>
    );
  }
  return (
    <div className="mx-auto max-w-xl rounded-lg border border-destructive/30 bg-card p-6 shadow-sm">
      <h1 className="text-xl font-semibold text-destructive">Authentication is not configured</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Production sign-in requires a real Clerk publishable key and secret key. Set
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY before exposing protected routes.
      </p>
      {issues.length ? (
        <div className="mt-5 space-y-2">
          {issues.map((issue) => (
            <div key={issue.code} className="rounded-md border bg-muted/40 p-3">
              <div className="font-mono text-xs font-semibold text-foreground">{issue.code}</div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{issue.message}</p>
            </div>
          ))}
        </div>
      ) : null}
      <p className="mt-5 text-sm leading-6 text-muted-foreground">
        After adding or changing these variables in Vercel, redeploy the production deployment so the
        server and middleware receive the new values.
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

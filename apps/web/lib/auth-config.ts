export const PLACEHOLDER_CLERK_PUBLISHABLE_KEY = "pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk";

export interface AuthConfigurationIssue {
  code: string;
  message: string;
}

export interface WebAuthConfiguration {
  publishableKey: string;
  publishableKeyConfigured: boolean;
  secretKeyConfigured: boolean;
  hasSecretKey: boolean;
  isProduction: boolean;
  authBypassRequested: boolean;
  clerkConfigured: boolean;
  issues: AuthConfigurationIssue[];
}

export function getWebAuthConfiguration(env: NodeJS.ProcessEnv = process.env): WebAuthConfiguration {
  const publishableKey = (env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "").trim();
  const secretKey = (env.CLERK_SECRET_KEY ?? "").trim();
  const isProduction = env.NODE_ENV === "production" || env.VERCEL_ENV === "production";
  const authBypassRequested = (env.AUTH_BYPASS ?? "").trim().toLowerCase() === "true";
  const publishableKeyConfigured = Boolean(publishableKey && publishableKey !== PLACEHOLDER_CLERK_PUBLISHABLE_KEY);
  const secretKeyConfigured = Boolean(secretKey && !secretKey.startsWith("replace-with-"));

  const issues: AuthConfigurationIssue[] = [];
  if (!publishableKeyConfigured) {
    issues.push({
      code: "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
      message: "Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY to the real Clerk publishable key for this Vercel environment."
    });
  }
  if (!secretKeyConfigured) {
    issues.push({
      code: "CLERK_SECRET_KEY",
      message: "Set CLERK_SECRET_KEY to the real Clerk secret key for this Vercel environment."
    });
  }
  if (isProduction && authBypassRequested) {
    issues.push({
      code: "AUTH_BYPASS",
      message: "AUTH_BYPASS must be false or unset in production. Development bypass is never allowed on Vercel production."
    });
  }

  return {
    publishableKey,
    publishableKeyConfigured,
    secretKeyConfigured,
    hasSecretKey: secretKeyConfigured,
    isProduction,
    authBypassRequested,
    clerkConfigured: issues.length === 0,
    issues
  };
}

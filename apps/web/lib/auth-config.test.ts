import { describe, expect, it } from "vitest";
import { getWebAuthConfiguration, PLACEHOLDER_CLERK_PUBLISHABLE_KEY } from "./auth-config";

describe("getWebAuthConfiguration", () => {
  it("requires real Clerk keys in production", () => {
    const config = getWebAuthConfiguration({
      NODE_ENV: "production",
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: PLACEHOLDER_CLERK_PUBLISHABLE_KEY,
      CLERK_SECRET_KEY: "replace-with-clerk-secret-key"
    });

    expect(config.isProduction).toBe(true);
    expect(config.clerkConfigured).toBe(false);
    expect(config.issues.map((issue) => issue.code)).toEqual([
      "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
      "CLERK_SECRET_KEY"
    ]);
  });

  it("blocks AUTH_BYPASS in Vercel production", () => {
    const config = getWebAuthConfiguration({
      NODE_ENV: "production",
      VERCEL_ENV: "production",
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "real-clerk-publishable-key",
      CLERK_SECRET_KEY: "real-clerk-secret-key",
      AUTH_BYPASS: "true"
    });

    expect(config.clerkConfigured).toBe(false);
    expect(config.issues.map((issue) => issue.code)).toContain("AUTH_BYPASS");
  });

  it("accepts real Clerk keys when production bypass is off", () => {
    const config = getWebAuthConfiguration({
      NODE_ENV: "production",
      NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "real-clerk-publishable-key",
      CLERK_SECRET_KEY: "real-clerk-secret-key",
      AUTH_BYPASS: "false"
    });

    expect(config.clerkConfigured).toBe(true);
    expect(config.issues).toEqual([]);
  });
});

import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.dirname(fileURLToPath(import.meta.url));
const initialEnv = new Set(Object.keys(process.env));

function loadEnvFile(envPath: string, override = false) {
  if (!fs.existsSync(envPath)) {
    return;
  }

  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = line.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }

    const [, key, rawValue] = match;
    if (initialEnv.has(key) || (!override && process.env[key] !== undefined)) {
      continue;
    }

    const value = rawValue.trim();
    process.env[key] = /^(['"]).*\1$/.test(value) ? value.slice(1, -1) : value;
  }
}

const mode = process.env.NODE_ENV === "production" ? "production" : process.env.NODE_ENV === "test" ? "test" : "development";
loadEnvFile(path.resolve(webRoot, "../..", ".env"));

for (const envFile of [".env", `.env.${mode}`, mode === "test" ? "" : ".env.local", `.env.${mode}.local`]) {
  if (envFile) {
    loadEnvFile(path.join(webRoot, envFile), true);
  }
}

const apiOrigin = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const clerkOrigins = "https://*.clerk.accounts.dev https://*.clerk.com";
const clerkCaptchaOrigins = "https://challenges.cloudflare.com";
const isProduction = process.env.NODE_ENV === "production";
const workspaceRoot = path.resolve(webRoot, "../..");
const scriptPolicy = isProduction
  ? `script-src 'self' 'unsafe-inline' ${clerkOrigins} ${clerkCaptchaOrigins}`
  : `script-src 'self' 'unsafe-inline' 'unsafe-eval' ${clerkOrigins} ${clerkCaptchaOrigins}`;

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  outputFileTracingRoot: workspaceRoot,
  turbopack: {
    root: workspaceRoot
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com"
      }
    ]
  },
  async headers() {
    const contentSecurityPolicy = [
      "default-src 'self'",
      "base-uri 'self'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      `connect-src 'self' ${apiOrigin} ${clerkOrigins}`,
      scriptPolicy,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://images.unsplash.com https://img.clerk.com",
      "font-src 'self' data:",
      "worker-src 'self' blob:",
      `frame-src ${clerkOrigins} ${clerkCaptchaOrigins}`,
      "object-src 'none'",
      isProduction ? "upgrade-insecure-requests" : ""
    ].filter(Boolean).join("; ");

    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" }
        ]
      }
    ];
  }
};

export default nextConfig;

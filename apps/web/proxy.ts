import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { getWebAuthConfiguration } from "@/lib/auth-config";

const authConfig = getWebAuthConfiguration();
const e2eSignedOutGuard = process.env.E2E_SIGNED_OUT_GUARD === "true";
const e2eSignedOutCookie = "mradi_e2e_signed_out";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/cases(.*)",
  "/admin(.*)",
  "/expert(.*)",
  "/settings(.*)",
  "/audit-log(.*)",
  "/reviews(.*)"
]);

const protectedMiddleware = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export default authConfig.clerkConfigured ? protectedMiddleware : function developmentProxy(req: NextRequest) {
  if (authConfig.isProduction && isProtectedRoute(req)) {
    return NextResponse.redirect(new URL("/configuration-error", req.url));
  }
  if (!authConfig.isProduction && e2eSignedOutGuard && isProtectedRoute(req) && req.cookies.get(e2eSignedOutCookie)?.value === "true") {
    return NextResponse.redirect(new URL("/sign-in", req.url));
  }
  return NextResponse.next();
};

export const config = {
  matcher: [
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)"
  ]
};

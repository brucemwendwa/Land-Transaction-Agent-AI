import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { getWebAuthConfiguration } from "@/lib/auth-config";

const authConfig = getWebAuthConfiguration();

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
  return NextResponse.next();
};

export const config = {
  matcher: [
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)"
  ]
};

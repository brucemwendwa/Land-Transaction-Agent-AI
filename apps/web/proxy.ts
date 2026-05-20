import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const placeholderClerkKey = "pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk";
const clerkConfigured =
  Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) &&
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY !== placeholderClerkKey;

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/cases(.*)",
  "/admin(.*)",
  "/settings(.*)",
  "/audit-log(.*)",
  "/reviews(.*)"
]);

const protectedMiddleware = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export default clerkConfigured ? protectedMiddleware : function developmentProxy() {
  return NextResponse.next();
};

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)"]
};

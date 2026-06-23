import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthConfigurationError } from "@/lib/auth";
import { getWebAuthConfiguration } from "@/lib/auth-config";
import { AUTH_REDIRECT_PATH } from "@/lib/auth-routes";

export const metadata: Metadata = {
  title: "Mradi wa Ardhi — Land Transaction Agent",
  description: "AI-assisted land transaction due diligence for buyers in Kenya.",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }]
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const authConfig = getWebAuthConfiguration();

  if (authConfig.isProduction && !authConfig.clerkConfigured) {
    return (
      <html lang="en" suppressHydrationWarning>
        <body>
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            <main className="flex min-h-screen items-center justify-center bg-background p-6">
              <AuthConfigurationError issues={authConfig.issues} />
            </main>
          </ThemeProvider>
        </body>
      </html>
    );
  }

  const appBody = authConfig.publishableKeyConfigured ? (
    <ClerkProvider
      publishableKey={authConfig.publishableKey}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl={AUTH_REDIRECT_PATH}
      signUpFallbackRedirectUrl={AUTH_REDIRECT_PATH}
    >
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        {children}
      </ThemeProvider>
    </ClerkProvider>
  ) : (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </ThemeProvider>
  );

  return (
    <html lang="en" suppressHydrationWarning>
      <body>{appBody}</body>
    </html>
  );
}

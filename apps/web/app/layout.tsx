import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthConfigurationError } from "@/lib/auth";
import { getWebAuthConfiguration } from "@/lib/auth-config";

export const metadata: Metadata = {
  title: "Mradi wa Ardhi — Land Transaction Agent",
  description: "AI-assisted land transaction due diligence for buyers in Kenya."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const authConfig = getWebAuthConfiguration();
  const body = (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );

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

  if (!authConfig.publishableKeyConfigured) {
    return body;
  }

  return (
    <ClerkProvider publishableKey={authConfig.publishableKey}>
      {body}
    </ClerkProvider>
  );
}

import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthConfigurationError } from "@/lib/auth";

const placeholderClerkKey = "pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk";
const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const clerkSecretKey = process.env.CLERK_SECRET_KEY;
const isProduction = process.env.NODE_ENV === "production";

export const metadata: Metadata = {
  title: "Mradi wa Ardhi — Land Transaction Agent",
  description: "AI-assisted land transaction due diligence for buyers in Kenya."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const body = (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );

  if (!clerkPublishableKey || clerkPublishableKey === placeholderClerkKey || (isProduction && !clerkSecretKey)) {
    if (isProduction) {
      return (
        <html lang="en" suppressHydrationWarning>
          <body>
            <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
              <main className="flex min-h-screen items-center justify-center bg-background p-6">
                <AuthConfigurationError />
              </main>
            </ThemeProvider>
          </body>
        </html>
      );
    }
    return body;
  }

  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      {body}
    </ClerkProvider>
  );
}

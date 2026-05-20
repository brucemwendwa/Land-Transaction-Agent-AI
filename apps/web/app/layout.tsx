import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

const placeholderClerkKey = "pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk";
const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

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

  if (!clerkPublishableKey || clerkPublishableKey === placeholderClerkKey) {
    return body;
  }

  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      {body}
    </ClerkProvider>
  );
}

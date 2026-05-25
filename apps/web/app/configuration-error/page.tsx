import { AuthConfigurationError } from "@/lib/auth";

export default function ConfigurationErrorPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <AuthConfigurationError />
    </main>
  );
}

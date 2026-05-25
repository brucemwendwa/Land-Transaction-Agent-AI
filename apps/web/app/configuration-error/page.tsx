import { AuthConfigurationError } from "@/lib/auth";
import { getWebAuthConfiguration } from "@/lib/auth-config";

export default function ConfigurationErrorPage() {
  const authConfig = getWebAuthConfiguration();

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <AuthConfigurationError issues={authConfig.issues} />
    </main>
  );
}

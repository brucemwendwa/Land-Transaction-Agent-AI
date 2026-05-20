import { AuthSignUp } from "@/lib/auth";

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <AuthSignUp />
    </main>
  );
}

import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <SignUp />
    </main>
  );
}

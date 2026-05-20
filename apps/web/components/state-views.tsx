import { AlertCircle, CheckCircle2, FileSearch, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <Card className="premium-panel">
      <CardContent className="flex flex-col items-start gap-4 p-6 sm:p-8">
        <div className="rounded-lg border bg-muted p-3">
          <Inbox className="h-6 w-6 text-primary" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-xl font-semibold">{title}</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="border-destructive/30 bg-destructive/5" role="alert">
      <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 text-destructive" aria-hidden="true" />
          <div>
            <h2 className="font-semibold text-destructive">Something needs attention</h2>
            <p className="mt-1 text-sm text-muted-foreground">{message}</p>
          </div>
        </div>
        {onRetry ? <Button variant="outline" onClick={onRetry}>Retry</Button> : null}
      </CardContent>
    </Card>
  );
}

export function SuccessState({ message, className }: { message: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-800 dark:text-emerald-200", className)}>
      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
      {message}
    </div>
  );
}

export function LoadingPanel({ label = "Loading workspace" }: { label?: string }) {
  return (
    <Card className="premium-panel">
      <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground" aria-live="polite">
        <FileSearch className="h-5 w-5 animate-pulse text-primary" aria-hidden="true" />
        {label}
      </CardContent>
    </Card>
  );
}

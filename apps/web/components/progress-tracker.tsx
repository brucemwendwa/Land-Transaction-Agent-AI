import { CheckCircle2, CircleDot } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  { key: "case", label: "Case" },
  { key: "documents", label: "Documents" },
  { key: "extraction", label: "Extraction" },
  { key: "analysis", label: "Analysis" },
  { key: "report", label: "Report" }
];

export function ProgressTracker({ current }: { current: string }) {
  const index = Math.max(0, steps.findIndex((step) => step.key === current));
  return (
    <div className="premium-panel grid grid-cols-5 gap-1 rounded-lg p-1 text-xs sm:gap-2 sm:p-2" aria-label="Case progress">
      {steps.map((step, stepIndex) => {
        const done = stepIndex <= index;
        return (
          <div
            key={step.key}
            className={cn(
              "flex min-h-11 items-center justify-center gap-1 rounded-md px-2 py-2 text-center font-medium transition-colors",
              done ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground"
            )}
            aria-current={step.key === current ? "step" : undefined}
          >
            {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">{step.label}</span>
          </div>
        );
      })}
    </div>
  );
}

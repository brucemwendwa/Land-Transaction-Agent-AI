import { ShieldAlert } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn, riskColor } from "@/lib/utils";

export function RiskMeter({ score, band }: { score: number; band: string }) {
  const normalized = Math.min(Math.max(score, 0), 100);
  const circumference = 2 * Math.PI * 44;
  const dash = circumference - (normalized / 100) * circumference;
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-5">
        <div className="relative h-28 w-28 shrink-0">
          <svg viewBox="0 0 112 112" className="h-28 w-28 -rotate-90" aria-hidden="true">
            <circle cx="56" cy="56" r="44" fill="none" stroke="currentColor" strokeWidth="10" className="text-muted" />
            <circle
              cx="56"
              cy="56"
              r="44"
              fill="none"
              stroke="currentColor"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dash}
              className={cn("transition-all duration-700", riskColor(score))}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className={cn("text-2xl font-semibold", riskColor(score))}>{score}</div>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">of 100</div>
            <span className="sr-only">{score}/100</span>
          </div>
        </div>
        <div className="min-w-0 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <ShieldAlert className="h-4 w-4" aria-hidden="true" />
            Risk score
          </div>
          <div className="text-sm text-muted-foreground">
            Current band: <span className="font-medium capitalize text-foreground">{band}</span>
            <span className="sr-only">Current band: {band}</span>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Low scores mean the uploaded evidence is more consistent. Higher scores mean the buyer should pause and escalate to professional review.
          </p>
        </div>
      </div>
      <Progress value={normalized} />
      <div className="grid grid-cols-4 gap-1 text-[11px] text-muted-foreground">
        <span>Low</span>
        <span>Medium</span>
        <span>High</span>
        <span>Critical</span>
      </div>
    </div>
  );
}

import { AlertTriangle, CheckCircle2, CircleDashed, ShieldQuestion } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type StatusTone = "verified" | "needs_review" | "not_verified" | "high_risk" | "neutral" | "success";

const toneMap: Record<StatusTone, { label: string; variant: "success" | "warning" | "danger" | "outline" | "info"; icon: typeof CheckCircle2 }> = {
  verified: { label: "Verified", variant: "success", icon: CheckCircle2 },
  needs_review: { label: "Needs review", variant: "warning", icon: AlertTriangle },
  not_verified: { label: "Not verified", variant: "outline", icon: ShieldQuestion },
  high_risk: { label: "High risk", variant: "danger", icon: AlertTriangle },
  neutral: { label: "In progress", variant: "info", icon: CircleDashed },
  success: { label: "Complete", variant: "success", icon: CheckCircle2 }
};

export function StatusBadge({ tone, label }: { tone: StatusTone; label?: string }) {
  const status = toneMap[tone];
  const Icon = status.icon;
  return (
    <Badge variant={status.variant} className="gap-1.5">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label ?? status.label}
    </Badge>
  );
}

export function statusToneFromValue(value: string): StatusTone {
  if (["verified", "clean", "extracted", "report_ready", "completed"].includes(value)) return "verified";
  if (["manual_review", "needs_review", "adapter_unavailable"].includes(value)) return "needs_review";
  if (["conflict_found", "rejected", "failed", "critical", "high"].includes(value)) return "high_risk";
  if (["not_verified_from_official_source", "not_verified"].includes(value)) return "not_verified";
  return "neutral";
}

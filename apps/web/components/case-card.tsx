import Link from "next/link";
import { ArrowRight, FileText, MapPin } from "lucide-react";
import type { ApiCase } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { StatusBadge, statusToneFromValue } from "@/components/status-badge";
import { formatDate } from "@/lib/utils";

const statusProgress: Record<string, number> = {
  draft: 12,
  documents_pending: 24,
  ready_for_analysis: 48,
  analyzing: 72,
  report_ready: 100,
  manual_review: 84,
  closed: 100
};

export function CaseCard({ landCase }: { landCase: ApiCase }) {
  const progress = statusProgress[landCase.status] ?? 20;
  return (
    <Card className="premium-panel transition-transform duration-200 hover:-translate-y-0.5">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{landCase.title}</CardTitle>
            <div className="mt-2 flex items-center gap-1 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4" />
              {landCase.location_county || "County not set"}
            </div>
          </div>
          <StatusBadge tone={statusToneFromValue(landCase.status)} label={landCase.status.replaceAll("_", " ")} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={progress} />
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-muted-foreground">Parcel</dt>
            <dd className="font-medium">{landCase.parcel_number_claimed || "Pending"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Documents</dt>
            <dd className="flex items-center gap-1 font-medium">
              <FileText className="h-3.5 w-3.5" aria-hidden="true" />
              {landCase.documents.length}
            </dd>
          </div>
        </dl>
        <div className="text-xs text-muted-foreground">Updated {formatDate(landCase.updated_at)}</div>
        <Link href={`/cases/${landCase.id}/upload`} className="focus-ring inline-flex rounded-md text-sm font-medium text-primary">
          Continue case <ArrowRight className="h-4 w-4" />
        </Link>
      </CardContent>
    </Card>
  );
}

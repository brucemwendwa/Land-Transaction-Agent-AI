import { LegalPage } from "@/components/legal-page";
import { legalPages } from "@/lib/legal";

export default function DataRetentionPage() {
  return <LegalPage {...legalPages.retention} />;
}

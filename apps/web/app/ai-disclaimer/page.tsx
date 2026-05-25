import { LegalPage } from "@/components/legal-page";
import { legalPages } from "@/lib/legal";

export default function AiDisclaimerPage() {
  return <LegalPage {...legalPages.aiDisclaimer} />;
}

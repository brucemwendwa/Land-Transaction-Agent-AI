import { LegalPage } from "@/components/legal-page";
import { legalPages } from "@/lib/legal";

export default function PrivacyPage() {
  return <LegalPage {...legalPages.privacy} />;
}

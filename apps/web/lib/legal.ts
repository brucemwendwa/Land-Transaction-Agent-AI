export const LEGAL_DISCLAIMER =
  "This report is an AI-assisted risk analysis. It does not replace an official land search, licensed advocate, licensed surveyor, Ardhisasa, Ministry of Lands, or National Land Commission verification.";

export const legalLinks = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/data-retention", label: "Data retention" },
  { href: "/ai-disclaimer", label: "AI disclaimer" }
];

export const legalPages = {
  terms: {
    eyebrow: "Terms of Service",
    title: "Terms of Service",
    sections: [
      {
        title: "Purpose",
        body: "Mradi wa Ardhi provides AI-assisted land transaction risk analysis using user-uploaded documents, extracted fields, public-source checks where configured, and deterministic risk rules."
      },
      {
        title: "No official verification claim",
        body: "The service does not claim official ownership verification unless the user uploads official evidence or an official integration returns verifiable results. A missing or unconfigured official source remains clearly marked."
      },
      {
        title: "User responsibilities",
        body: "Users must have permission to upload documents, must not upload unlawful material, and should obtain professional and official checks before paying deposits, signing completion documents, or relying on the report."
      },
      {
        title: "Human review",
        body: "Advocate, surveyor, site visit, boundary verification, and official-search assistance workflows are request and coordination workflows. They do not guarantee a legal opinion unless a licensed professional separately provides one."
      }
    ]
  },
  privacy: {
    eyebrow: "Privacy Policy",
    title: "Privacy Policy",
    sections: [
      {
        title: "Data processed",
        body: "The app processes account details, case details, uploaded documents, extracted fields, user corrections, audit events, review notes, payment status, and generated reports."
      },
      {
        title: "Private storage",
        body: "Uploaded files are stored in private storage. Production deployments should use Google Cloud Storage signed URLs; public file URLs are not exposed."
      },
      {
        title: "Access control",
        body: "Case owners, assigned experts, and administrators can access relevant records according to their role. Expert users should only see cases assigned to them."
      },
      {
        title: "Third-party providers",
        body: "Configured providers may include Clerk for authentication, Google Cloud Storage, Document AI, Gemini or Vertex AI, Gazette source adapters, malware scanning, email delivery, and M-Pesa Daraja payments."
      }
    ]
  },
  retention: {
    eyebrow: "Data Retention Policy",
    title: "Data Retention Policy",
    sections: [
      {
        title: "Case records",
        body: "Case metadata, extracted fields, corrections, audit logs, and generated reports should be retained only for the period required by the customer workflow, contract, or law."
      },
      {
        title: "Uploaded files",
        body: "Production storage should define lifecycle rules for quarantine objects, completed case evidence, stale generated PDFs, and deleted-case cleanup."
      },
      {
        title: "Deletion handling",
        body: "The API includes file deletion support through the storage adapter. Deleting a case should remove related private objects where permitted by retention obligations."
      },
      {
        title: "Audit records",
        body: "Audit records should be retained long enough to investigate access, payment, report generation, review assignment, and file-handling activity."
      }
    ]
  },
  aiDisclaimer: {
    eyebrow: "AI Disclaimer",
    title: "AI Disclaimer",
    sections: [
      {
        title: "Evidence-based analysis",
        body: "The AI agent must answer only from uploaded documents, extracted fields, Gazette results, and risk analysis. It must not infer official ownership or fabricate verification."
      },
      {
        title: "Provider configuration",
        body: "If OCR, AI extraction, Gazette search, malware scanning, payments, or official-source adapters are missing credentials, the app should show a not-configured status instead of fake results."
      },
      {
        title: "Decision support",
        body: "Risk reports help buyers and professionals identify warning signs, missing evidence, and next steps. They do not replace official searches or licensed professional advice."
      },
      {
        title: "Required disclaimer",
        body: LEGAL_DISCLAIMER
      }
    ]
  }
} as const;

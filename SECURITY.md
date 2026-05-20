# Security Policy

## Data Handled

Mradi wa Ardhi handles land transaction due-diligence data, including case metadata, party names, parcel/title references, uploaded land documents, extracted document fields, risk factors, reports, audit events, and optional reviewer/payment records.

Uploaded land documents are private case data. They must be stored in a private bucket or private local volume and accessed only through short-lived signed URLs or authenticated API responses. Do not place uploaded documents in public web roots, public object buckets, frontend bundles, analytics tools, or client-side logs.

## Threat Model

Primary risks include:

- Unauthorized access to another user's case or documents.
- Public exposure of uploaded title deeds, ID documents, KRA PINs, agreements, searches, maps, or reports.
- Forged or oversized uploads, unsupported file types, and malware-bearing files.
- Token theft, weak production configuration, or accidental authentication bypass.
- Cross-site request forgery on cookie-authenticated unsafe requests.
- Excessive API traffic or upload abuse.
- Leakage of sensitive document contents into logs, traces, frontend code, or audit records.
- Overreliance on AI output as legal advice or official registry verification.

## Security Controls

- Clerk JWT bearer authentication with RS256 token verification.
- Role-based access control for admin-only routes.
- Case-level authorization so non-admin users can access only their own cases and matching review requests.
- Private storage keys are not returned in document API responses; uploaded files and reports are delivered through authenticated endpoints or short-lived signed URLs only.
- Uploads use signed URLs, quarantine storage, declared type validation, content signature validation, SHA-256 integrity checks, configured size limits, and a malware scanning hook.
- Downloads are authenticated or short-lived signed URLs, download responses use `Cache-Control: no-store`, and download events are audit logged.
- CORS is restricted to configured origins and production rejects wildcard origins.
- Conditional CSRF protection is enforced for unsafe requests made with cookies.
- Rate limiting is enabled at the API middleware layer.
- Request bodies use Pydantic validation with forbidden extra fields for mutating APIs.
- Production startup rejects authentication bypass, missing Clerk settings, weak signing secrets, insecure public URLs, wildcard CORS, and development database defaults.
- Security headers are set for API and web responses: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
- Audit logs are recorded for login, file upload, extraction, risk analysis, report generation, download, admin access, and deletion.
- Audit metadata and agent audit traces redact document contents and common PII fields.
- Raw extraction payload persistence is disabled by default. Keep `PERSIST_RAW_EXTRACTION_PAYLOADS=false` unless a tightly controlled investigation requires otherwise.
- Upload consent is required before document upload.
- Legal disclaimer acceptance is required before report generation.
- Case deletion removes database case data and attempts to delete related stored documents/reports.

## Route Protection Summary

Public operational endpoints:

- `GET /healthz`
- `GET /health`
- `GET /readyz`

Authenticated user endpoints:

- `/auth/*`
- `/cases/*`
- `/documents/*`
- `/uploads/signed-url`
- `/uploads/complete`
- `/reviews`
- `/audit-logs`
- `/pricing/selection`
- `/api/cases/*`

Admin-only endpoints:

- `/admin/*`
- `/audit-logs/admin`

Signed transfer endpoints:

- `PUT /uploads/local/{document_id}`
- `GET /uploads/local-read`

The signed transfer endpoints are used by the local development storage provider. They require a valid expiring HMAC token and are disabled when the active storage provider is not local. Production uses private GCS signed URLs and authenticated report downloads.

## Encryption At Rest

Use managed encryption at rest for the production database and object storage. For Google Cloud Storage, keep buckets private, use uniform bucket-level access, disable public ACLs, and prefer CMEK where the deployment requires customer-managed keys. For PostgreSQL, use encrypted disks or a managed encrypted database service, restrict backups, and encrypt database snapshots.

Local storage is suitable for development only. Production deployments should use private object storage with service-account access scoped to the application.

## PII Minimization

Collect only fields needed for land transaction review. Avoid uploading unnecessary identity pages or unrelated documents. Do not log document bodies, OCR text, extracted source snippets, IDs, PINs, phone numbers, or reviewer emails. Keep audit logs focused on action metadata, IDs, status, score bands, and operational outcomes.

Generated reports and extracted fields may contain personal or land-identifying information. Treat them as confidential case data and apply retention/deletion policies.

## Responsible Disclosure

Report suspected vulnerabilities privately to the maintainers. Include:

- Affected endpoint, page, or configuration.
- Reproduction steps.
- Impact and any data exposure risk.
- Suggested remediation, if known.

Do not access, download, modify, or disclose another user's land documents or personal data while testing.

## Limitations

This system is AI-assisted decision support. It is not legal advice, not a licensed advocate or surveyor, and not official Ministry of Lands, National Land Commission, or registry verification. Malware scanning depends on the configured scanner service. Rate limiting is in-memory by default and should be replaced with a shared store such as Redis for multi-instance production deployments.

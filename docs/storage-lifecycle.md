# Storage Lifecycle Policy

Mradi wa Ardhi stores land transaction documents and generated reports as private objects. Production deployments should use Google Cloud Storage with signed URLs only.

## Buckets and prefixes

- `quarantine/`: newly uploaded files before validation and malware scanning.
- `clean/`: files that passed validation and are available for extraction.
- `reports/`: generated PDF reports.

## Recommended lifecycle rules

- Delete abandoned `quarantine/` objects after 24 hours.
- Retain `clean/` evidence according to the customer contract, consent, legal hold, and audit requirements.
- Delete stale generated reports after 90 days unless the case remains active.
- Delete objects when a case is deleted, unless retention obligations require preserving audit evidence.
- Keep bucket access private; do not enable public object access.

## Required metadata in the database

Each document record should retain `storage_key`, `bucket`, `file_size`, `mime_type`, `sha256`, and `uploaded_by_user_id`. Download access should be issued through short-lived signed URLs and audited.

## Operational notes

- Run malware scanning before moving an object from `quarantine/` to `clean/`.
- Treat `scan_status=not_configured` as an admin warning, not a clean security signal.
- Rotate signed URL secrets and Google Cloud service-account credentials through the deployment secret manager.

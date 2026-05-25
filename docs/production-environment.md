# Production Environment Variables

Use Secret Manager for Cloud Run secrets and Vercel environment variables for the web app. Do not commit real values.

## Backend: Cloud Run

Required application settings:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `APP_ENV` | Yes | Set to `production`. |
| `FRONTEND_URL` | Yes | Public Vercel URL, for example `https://mradi.example.com`. |
| `BACKEND_URL` | Yes | Public API URL, for example `https://mradi-api-...run.app`. |
| `CORS_ORIGINS` | Yes | Comma-separated browser origins. Do not include `*`. |
| `DATABASE_URL` | Yes | PostgreSQL URL for Neon, Supabase Postgres, or Cloud SQL. Use `sslmode=require` for managed public Postgres. |
| `AUTO_CREATE_TABLES` | Yes | Set to `false`; run Alembic migrations explicitly. |

Authentication:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `AUTH_BYPASS` | Yes | Must be `false`. Production startup rejects `true`. |
| `CLERK_ISSUER` | Yes | Clerk issuer URL. |
| `CLERK_JWKS_URL` | Yes | Clerk JWKS URL. |
| `CLERK_AUDIENCE` | If configured | Required only when the Clerk token audience is enforced. |
| `AUTH_ALLOWED_ALGORITHM` | Yes | Keep `RS256`. Production startup rejects other values. |
| `AUTH_SECRET` | Yes | Strong random value, at least 32 characters. Used as the fallback for upload/report signing secrets. |

Signing and request security:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `UPLOAD_SIGNING_SECRET` | Yes | Strong random value, at least 32 characters. May be omitted only when `AUTH_SECRET` is used as fallback. |
| `REPORT_SIGNING_SECRET` | Yes | Strong random value, at least 32 characters. May be omitted only when `AUTH_SECRET` is used as fallback. |
| `CSRF_COOKIE_NAME` | Yes | Default `csrf_token`. |
| `CSRF_HEADER_NAME` | Yes | Default `x-csrf-token`. |
| `CONTENT_SECURITY_POLICY` | Yes | API response CSP. Keep restrictive unless an integration requires a reviewed exception. |
| `RATE_LIMIT_PER_MINUTE` | Yes | Start with `120`; replace process-local limiting with Redis or gateway limits for multi-instance production. |

Storage:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `STORAGE_BACKEND` | Yes | Set to `gcs`. Production startup rejects other values. |
| `GCS_BUCKET_NAME` | Yes | Private GCS bucket for uploads and reports. |
| `GOOGLE_CLOUD_PROJECT` | Yes | Google Cloud project ID. |
| `GOOGLE_APPLICATION_CREDENTIALS` | No on Cloud Run | Use only for local development or non-GCP hosting. Cloud Run should use its service account. |
| `LOCAL_STORAGE_ROOT` | Local only | Development storage path. Do not use in production. |

Upload and malware scanning:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `MAX_UPLOAD_BYTES` | Yes | Default `25000000`. Match the frontend value. |
| `MAX_LOCAL_UPLOAD_MEMORY_BYTES` | Local only | Local upload memory guard; default `1048576`. |
| `ENABLE_MALWARE_SCAN` | Yes | Set to `true` only when ClamAV is reachable and monitored. |
| `CLAMD_HOST` | If scanning | ClamAV host. |
| `CLAMD_PORT` | If scanning | ClamAV port, default `3310`. |
| `PERSIST_RAW_EXTRACTION_PAYLOADS` | Yes | Keep `false` unless a controlled investigation temporarily requires raw payload retention. |

AI, OCR, and agents:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | Set to `true` when using Vertex AI identity. |
| `VERTEX_AI_LOCATION` | Yes | Vertex AI region, for example `us-central1`. |
| `GEMINI_MODEL` | Yes | Default `gemini-2.5-flash`; review model choice before production changes. |
| `DOCUMENT_AI_PROCESSOR_ID` | Yes for OCR | Leave empty only when OCR is intentionally disabled. |
| `DOCUMENT_AI_LOCATION` | Yes for OCR | Document AI location, for example `us` or `eu`. |
| `GEMINI_API_KEY` | Alternative auth | Use only when not using Vertex AI identity. |
| `VERTEX_AI_AGENT_ENGINE_RESOURCE` | Optional | Existing Agent Engine resource when the release process uses hosted agents. |
| `ADK_AGENT_CONFIG` | Optional | Path, resource name, or JSON pointer used by the Agent Engine release process. |
| `STATE_DEPARTMENT_LANDS_GAZETTE_URL` | Optional | Partner/public Gazette source URL when available. |

Observability:

| Variable | Required | Production guidance |
| --- | --- | --- |
| `LOG_LEVEL` | Yes | Use `INFO` by default. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional | OTLP collector endpoint. |
| `SENTRY_DSN` | Optional | Optional Sentry project DSN. |
| `SENTRY_TRACES_SAMPLE_RATE` | Optional | Start at `0.0` or a low value such as `0.05`. |
| `SENTRY_PROFILES_SAMPLE_RATE` | Optional | Start at `0.0` unless profiling has been approved. |

Accepted compatibility aliases:

| Production name | Existing alias |
| --- | --- |
| `FRONTEND_URL` | `PUBLIC_APP_URL` |
| `BACKEND_URL` | `API_BASE_URL` |
| `GOOGLE_CLOUD_PROJECT` | `GCP_PROJECT_ID` |
| `GCS_BUCKET_NAME` | `GCS_BUCKET` |
| `GEMINI_API_KEY` | `GOOGLE_API_KEY` |
| `DOCUMENT_AI_LOCATION` | `GCP_LOCATION` |
| `SENTRY_DSN` | `ERROR_MONITORING_DSN` |

## Frontend: Vercel

Required:

| Variable | Notes |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Cloud Run backend URL, with no trailing slash. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key. |
| `CLERK_SECRET_KEY` | Clerk secret key. |
| `AUTH_BYPASS` | Must be unset or `false` in production. `true` is rejected by the web auth gate. |
| `NEXT_PUBLIC_MAX_UPLOAD_BYTES` | Match backend `MAX_UPLOAD_BYTES`. |

See [Vercel Clerk Authentication Setup](./vercel-clerk-auth.md) for exact Vercel dashboard steps and redeploy instructions.

## Secret Storage

Create Cloud Run secrets for values that should not appear in YAML:

```bash
printf "%s" "$DATABASE_URL" | gcloud secrets create mradi-database-url --data-file=-
printf "%s" "$AUTH_SECRET" | gcloud secrets create mradi-auth-secret --data-file=-
printf "%s" "$CLERK_ISSUER" | gcloud secrets create mradi-clerk-issuer --data-file=-
printf "%s" "$CLERK_JWKS_URL" | gcloud secrets create mradi-clerk-jwks-url --data-file=-
printf "%s" "$UPLOAD_SIGNING_SECRET" | gcloud secrets create mradi-upload-signing-secret --data-file=-
printf "%s" "$REPORT_SIGNING_SECRET" | gcloud secrets create mradi-report-signing-secret --data-file=-
```

For an existing secret, add a new version:

```bash
printf "%s" "$DATABASE_URL" | gcloud secrets versions add mradi-database-url --data-file=-
```

## Production Guardrails

Production startup rejects:

- `AUTH_BYPASS=true`
- missing Clerk issuer or JWKS URL
- non-HTTPS frontend or backend URLs
- wildcard CORS origins
- weak or development signing secrets
- local/default database URLs
- `AUTO_CREATE_TABLES=true`
- non-GCS storage

Keep uploaded documents and generated reports in private storage. API responses should return document metadata, authenticated report downloads, or short-lived signed URLs only.

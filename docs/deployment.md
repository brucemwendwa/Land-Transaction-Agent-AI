# Deployment Guide

This guide deploys Mradi wa Ardhi with Vercel for the web app, Cloud Run for the API, managed PostgreSQL, GCS, and Vertex AI/Document AI.

## 1. Local Setup

```bash
cp .env.example .env
docker compose up -d postgres
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up api web
```

Open:

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/healthz`
- API readiness: `http://localhost:8000/readyz`

Run the development seed only after migrations:

```bash
docker compose exec api python -m app.db.seed
```

Without Docker for the app services:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,security]"
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then, in another terminal:

```bash
pnpm install
pnpm --filter @mradi/web dev
```

## 2. Cloud Setup

Set deployment variables:

```bash
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"
export ARTIFACT_REPO="mradi"
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$ARTIFACT_REPO/api:latest"
export SERVICE_ACCOUNT="mradi-api-runtime@$PROJECT_ID.iam.gserviceaccount.com"
```

Choose a database:

- Neon or Supabase Postgres: copy the pooled PostgreSQL URL and include `sslmode=require`; the API accepts `postgres://`, `postgresql://`, and `postgresql+psycopg://` URLs.
- Cloud SQL Postgres: create a PostgreSQL instance, database, and user, then use either private IP or the Cloud SQL connector path documented by Google.

Create a GCS bucket:

```bash
gcloud storage buckets create "gs://mradi-prod-documents" \
  --project "$PROJECT_ID" \
  --location "$REGION" \
  --uniform-bucket-level-access
```

Create the runtime service account:

```bash
gcloud iam service-accounts create mradi-api-runtime \
  --project "$PROJECT_ID" \
  --display-name "Mradi API Runtime"
```

Grant minimum starting roles:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/logging.logWriter

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/cloudtrace.agent

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/secretmanager.secretAccessor

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/aiplatform.user

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/documentai.apiUser

gcloud storage buckets add-iam-policy-binding "gs://mradi-prod-documents" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/storage.objectAdmin
```

For GCS V4 signed URLs on Cloud Run, enable IAM Credentials and allow the runtime service account to sign as itself when required by your organization policy:

```bash
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/iam.serviceAccountTokenCreator \
  --project "$PROJECT_ID"
```

If using Cloud SQL, also grant:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$SERVICE_ACCOUNT" \
  --role roles/cloudsql.client
```

## 3. Google Cloud APIs To Enable

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudtrace.googleapis.com \
  clouderrorreporting.googleapis.com \
  --project "$PROJECT_ID"
```

Enable this as well when using Cloud SQL:

```bash
gcloud services enable sqladmin.googleapis.com --project "$PROJECT_ID"
```

## 4. How To Run Migrations

Build the API image first:

```bash
gcloud artifacts repositories create "$ARTIFACT_REPO" \
  --repository-format=docker \
  --location "$REGION" \
  --project "$PROJECT_ID"

gcloud builds submit apps/api --tag "$IMAGE" --project "$PROJECT_ID"
```

Create a Cloud Run Job for migrations:

```bash
gcloud run jobs create mradi-api-migrate \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars APP_ENV=production,AUTO_CREATE_TABLES=false,FRONTEND_URL=https://YOUR_VERCEL_DOMAIN,BACKEND_URL=https://YOUR_CLOUD_RUN_DOMAIN,CORS_ORIGINS=https://YOUR_VERCEL_DOMAIN,AUTH_BYPASS=false,STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=mradi-prod-documents,GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
  --set-secrets DATABASE_URL=mradi-database-url:latest,AUTH_SECRET=mradi-auth-secret:latest,CLERK_ISSUER=mradi-clerk-issuer:latest,CLERK_JWKS_URL=mradi-clerk-jwks-url:latest \
  --command alembic \
  --args upgrade,head
```

After the first creation, use `gcloud run jobs update` with the same flags when the image or environment changes.

Execute migrations:

```bash
gcloud run jobs execute mradi-api-migrate \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --wait
```

Local migration command:

```bash
cd apps/api
alembic upgrade head
```

Development seed command, never production:

```bash
cd apps/api
python -m app.db.seed
```

## 5. How To Deploy Frontend

The repo includes `vercel.json` for the monorepo build.

Set Vercel production variables:

```bash
vercel env add NEXT_PUBLIC_API_URL production
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production
vercel env add CLERK_SECRET_KEY production
vercel env add NEXT_PUBLIC_MAX_UPLOAD_BYTES production
```

Deploy:

```bash
pnpm install --frozen-lockfile
pnpm --filter @mradi/web build
vercel --prod
```

In the Vercel project settings, keep the project root at the repository root when using the included `vercel.json`.

## 6. How To Deploy Backend

Update `infra/cloudrun-api.yaml` placeholders:

- `PROJECT_ID`
- `REGION`
- `YOUR_VERCEL_DOMAIN`
- `YOUR_CLOUD_RUN_DOMAIN`
- `mradi-prod-documents`
- `YOUR_PROCESSOR_ID`
- Cloud SQL annotation, if using Cloud SQL

Deploy from the YAML:

```bash
gcloud run services replace infra/cloudrun-api.yaml \
  --region "$REGION" \
  --project "$PROJECT_ID"
```

Or deploy with flags:

```bash
gcloud run deploy mradi-api \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --set-env-vars APP_ENV=production,AUTO_CREATE_TABLES=false,FRONTEND_URL=https://YOUR_VERCEL_DOMAIN,BACKEND_URL=https://YOUR_CLOUD_RUN_DOMAIN,CORS_ORIGINS=https://YOUR_VERCEL_DOMAIN,STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=mradi-prod-documents,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=true,VERTEX_AI_LOCATION=us-central1,DOCUMENT_AI_LOCATION=us,DOCUMENT_AI_PROCESSOR_ID=YOUR_PROCESSOR_ID,GEMINI_MODEL=gemini-2.5-flash \
  --set-secrets DATABASE_URL=mradi-database-url:latest,AUTH_SECRET=mradi-auth-secret:latest,CLERK_ISSUER=mradi-clerk-issuer:latest,CLERK_JWKS_URL=mradi-clerk-jwks-url:latest
```

For Vertex AI Agent Engine preparation:

```bash
GOOGLE_CLOUD_PROJECT="$PROJECT_ID" PYTHONPATH=apps/api python infra/deploy-agent-engine.py
```

Use your organization’s Agent Engine release workflow to publish the ADK agents when the target runtime is approved.

## 7. How To Test Production

Run release checks before deployment:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build

cd apps/api
.venv/bin/ruff check app tests
.venv/bin/mypy app
.venv/bin/pytest
```

Smoke test the API:

```bash
export BACKEND_URL="https://YOUR_CLOUD_RUN_DOMAIN"
curl -fsS "$BACKEND_URL/healthz"
curl -fsS "$BACKEND_URL/readyz"
```

Check Cloud Run logs:

```bash
gcloud run services logs read mradi-api \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --limit 50
```

Verify the web app:

```bash
export FRONTEND_URL="https://YOUR_VERCEL_DOMAIN"
curl -I "$FRONTEND_URL"
```

End-to-end production checks:

- Sign in with a real Clerk user.
- Create a case.
- Upload a small PDF.
- Confirm the object lands in the GCS bucket under `quarantine/`, then moves to `clean/` after upload completion.
- Run extraction and confirm Document AI or Gemini fields appear when configured.
- Run risk analysis and generate a report.
- Confirm Cloud Logging shows JSON `request.completed` events with `request_id`.

## Logging And Error Monitoring

The API writes structured JSON logs to stdout. Cloud Run forwards these to Cloud Logging automatically.

Unhandled request exceptions are logged as `request.failed` with stack traces. With `clouderrorreporting.googleapis.com` enabled, Cloud Error Reporting can group these failures from Cloud Logging.

Optional Sentry setup:

```bash
gcloud secrets create mradi-sentry-dsn --data-file=-
```

Then add `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, and `SENTRY_PROFILES_SAMPLE_RATE` to Cloud Run. Keep sample rates low until traffic patterns are known.

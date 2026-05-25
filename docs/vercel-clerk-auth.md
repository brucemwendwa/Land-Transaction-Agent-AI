# Vercel Clerk Authentication Setup

Mradi wa Ardhi uses Clerk for production web authentication. The Vercel web deployment must have both Clerk keys configured:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`

The production app will show a setup error instead of protected screens when either key is missing, still set to the placeholder value, or when `AUTH_BYPASS=true`.

## Get Clerk Keys

1. Open the Clerk Dashboard.
2. Select the Mradi wa Ardhi Clerk application.
3. Go to **Configure** -> **API keys**.
4. Copy the **Publishable key** for the environment you are deploying.
   - Production should normally use a `pk_live_...` key.
   - Preview deployments may use the Clerk environment you intentionally choose.
5. Copy the **Secret key** for the same Clerk environment.
   - Production should normally use an `sk_live_...` key.

Do not use the placeholder key from `.env.example` in Vercel.

## Add Variables In Vercel Dashboard

1. Open the Vercel Dashboard.
2. Select the Mradi wa Ardhi project.
3. Go to **Settings** -> **Environment Variables**.
4. Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
   - Value: the Clerk publishable key, for example `pk_live_...`.
   - Environments: select **Production**. Select **Preview** only if that Clerk key is intended for preview deployments.
5. Add `CLERK_SECRET_KEY`.
   - Value: the matching Clerk secret key, for example `sk_live_...`.
   - Environments: select the same environments as the publishable key.
6. Remove `AUTH_BYPASS` from **Production**, or set its production value to `false`.
   - Never set `AUTH_BYPASS=true` for a production Vercel environment.
7. Confirm the values do not include quotes, trailing spaces, or the placeholders from `.env.example`.

## Redeploy After Changing Variables

Vercel does not change an already-built deployment when you edit environment variables. Redeploy after saving the variables:

1. In Vercel, open **Deployments**.
2. Open the latest production deployment.
3. Click **Redeploy**.
4. If the same setup error remains, redeploy again without the build cache or push a new commit to trigger a fresh production build.

## CLI Alternative

From a machine logged in to the correct Vercel team and project:

```bash
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production
vercel env add CLERK_SECRET_KEY production
vercel env rm AUTH_BYPASS production
printf "false" | vercel env add AUTH_BYPASS production
vercel --prod
```

If `AUTH_BYPASS` was not set in production, the remove command can fail safely. The important state is that production has no `AUTH_BYPASS=true` value.

## What The App Checks

In production, the web app requires:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is present and not the sample placeholder.
- `CLERK_SECRET_KEY` is present and not the sample placeholder.
- `AUTH_BYPASS` is unset or set to `false`.

If one of those checks fails, the app shows a clear configuration error instead of pretending authentication is available.

The backend API also needs Clerk authentication configured in its own hosting environment. For Cloud Run, keep `AUTH_BYPASS=false` and set the Clerk issuer/JWKS values documented in `docs/production-environment.md`.

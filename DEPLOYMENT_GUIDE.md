# Deployment Runbook: Vercel + Render + MongoDB Atlas

This is the exact sequence for connecting the Vercel frontend to a persistent FastAPI backend. The backend URL is unknown until the Render service is created, so **do not add a fake URL to Vercel**.

## Architecture

- Vercel: Next.js UI, session login, same-origin API proxy, OpenAPI Actions schema.
- Render web service: FastAPI API from the repository root Dockerfile.
- Render worker service: `python -m acios.worker`, deployed from the same repository/image.
- MongoDB Atlas: durable organizations, contacts, drafts, approvals, and job records.
- Private S3-compatible bucket: shared resume storage for the separate API and worker services.
- Keep live email disabled during setup; use `DRY_RUN=true`.

## Step 1 — Secure GitHub first

1. Keep the repository private while you clean up history and rotate credentials.
2. Files removed from the current tree may still exist in old commits, forks, clones, and caches. Rewrite history with `git-filter-repo` only after coordinating with any other clones.
3. Rotate every credential that was committed or may have been exposed.
4. Review and merge this deployment PR only after its CI and Render Blueprint validation pass.

## Step 2 — Create MongoDB Atlas

1. Create a dedicated production cluster and database user for ACIOS.
2. Create a database named `acios_production`.
3. Copy the Atlas connection string. Replace the password placeholder and URL-encode any special characters.
4. Restrict network access to the backend and worker's egress IPs when feasible. Do not commit the URI.
5. The connection string becomes the Render secret `MONGODB_URI`; do not put it in Vercel.

## Step 3 — Create private resume storage

Create a private S3-compatible bucket. Do not enable public access. Create an access key restricted to that bucket with object read/write permissions for the ACIOS resume key. For AWS S3, use the bucket's region; for an S3-compatible provider, use its endpoint URL and region.

Required backend/worker variables:
- `RESUME_STORAGE_BACKEND=s3`
- `RESUME_STORAGE_BUCKET=<private-bucket-name>`
- `RESUME_STORAGE_REGION=<bucket-region>`
- `RESUME_STORAGE_ENDPOINT_URL=<provider-endpoint>` (leave blank for AWS S3)
- `AWS_ACCESS_KEY_ID=<restricted-access-key>`
- `AWS_SECRET_ACCESS_KEY=<restricted-secret>`

Both services must use the same bucket and credentials.

## Step 4 — Deploy the Render Blueprint

1. In Render, choose **New → Blueprint** and connect this GitHub repository.
2. Select branch `deploy/render-backend-blueprint` to test the deployment PR, or select `main` after its changes have been merged.
3. Render reads `render.yaml` and proposes two services: `acios-api` and `acios-worker`, plus a shared secret group.
4. Enter `ACIOS_BACKEND_API_KEY` and `MONGODB_URI` in the secret group. Generate the backend key locally with:
   ```bash
   openssl rand -hex 32
   ```
   Save it in a password manager. Use the exact same value for Render's `ACIOS_BACKEND_API_KEY` and Vercel's variable of that name.
5. Enter the private bucket name and S3 credentials in the shared group. Optional provider credentials can be left unset if you are not using those integrations.
6. Keep `DRY_RUN=true`. Deploy both services.
7. Wait for `acios-api` to become healthy. Open its Render service details and copy its **HTTPS public URL**. It should serve `GET /healthz`.
8. Confirm the worker stays running and reports its storage engine as MongoDB in logs. If either service fails, inspect its logs before configuring Vercel.

Do not turn on live SMTP. The initial Render template intentionally does not enable live sending.

## Step 5 — Add Vercel environment variables

Open **Vercel → Project → automation-carrer-outreach → Settings → Environment Variables**. Add these to **Production**. Use different values and a separate non-production backend for Preview; never point Preview at production data.

| Variable | Exact value | Where used |
| --- | --- | --- |
| `ACIOS_BACKEND_URL` | The HTTPS URL copied from the deployed `acios-api` Render service, without a trailing slash | Vercel server-side proxy |
| `ACIOS_BACKEND_API_KEY` | The same random value set on Render's API and worker secret group | Authenticates Vercel-to-FastAPI requests |
| `ACIOS_UI_PASSWORD` | A unique password of at least 20 characters | Private web cockpit login |
| `ACIOS_SESSION_SECRET` | A separate random secret, at least 32 characters | Signs the HTTP-only login session |
| `ACIOS_API_KEY` | A separate random secret, at least 32 characters | OpenAPI Actions bearer token; also configure this value in ChatGPT Actions |

Generate the three non-backend secrets locally using separate invocations:
```bash
openssl rand -hex 32  # ACIOS_SESSION_SECRET
openssl rand -hex 32  # ACIOS_API_KEY
openssl rand -hex 32  # use as a basis for a unique ACIOS_UI_PASSWORD if desired
```
For `ACIOS_UI_PASSWORD`, a password manager can generate a long unique password; do not reuse your login password. Keep every variable server-side and never prefix them with `NEXT_PUBLIC_`. Choose Vercel's Sensitive/Encrypted type where available.

Do not set `ACIOS_MCP_BEARER_TOKEN` for ChatGPT remote MCP yet. The current MCP route uses static bearer auth, not the OAuth authorization flow needed for a production ChatGPT custom remote MCP connection. OpenAPI Actions is the currently documented token-based integration.

## Step 6 — Redeploy Vercel

After saving the variables, trigger a new **Production** deployment from `main`. Environment changes do not alter already-built deployments. Verify the deployment target is Production and inspect build logs.

## Step 7 — Verify the connection without sending email

1. Open the production Vercel URL. Confirm the login page appears.
2. Sign in using `ACIOS_UI_PASSWORD`.
3. Open the system stats/dashboard. If the UI shows a backend connection error, check that `ACIOS_BACKEND_URL` is correct, HTTPS works, and `ACIOS_BACKEND_API_KEY` exactly matches Render.
4. Call Render's `GET /healthz`. It should return JSON with `status: ok` and `storage_engine: mongodb`.
5. A direct request to a protected backend route without a bearer token must return `401`; an unconfigured backend key should return `503`.
6. Check Render logs for MongoDB connection errors and worker startup failures.
7. Configure ChatGPT Actions with the production server URL and `ACIOS_API_KEY`. Import the OpenAPI schema from `https://<your-vercel-domain>/api/openapi.json`. Test read-only company search and dossier lookup first.
8. Create a test outreach draft. Confirm it stays `PENDING_APPROVAL` until you approve it in the signed-in cockpit. Then test the send workflow with `DRY_RUN=true`; it must report `DRY_RUN`, leave the draft `APPROVED`, create no dispatch lock, and send no email.
9. Confirm a job changes from `QUEUED` to `COMPLETED` in the job status endpoint and that the worker logs show it processed the job.

## Step 8 — Do not enable live email until all gates pass

Only after successful smoke tests, verified suppression behavior, resume storage checks, worker restart/recovery tests, and explicit approval/audit checks should you consider setting `DRY_RUN=false` on **both** Render services. Set Gmail sender credentials only in Render's secret manager, never in Vercel. A send with an ambiguous SMTP result must require manual reconciliation; never blindly retry it.

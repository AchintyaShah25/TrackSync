---
name: deploy
description: Deploy the app (migrations, API, web) and verify it. Only run when the user invokes /deploy.
disable-model-invocation: true
---

# Deploy

1. Confirm the working tree is clean and on `main`, and CI is green for the latest commit.
2. Run `make lint` and `make test` locally; stop on any failure.
3. Show the user any migrations in `supabase/migrations/` not yet applied to the hosted
   project, and ask for confirmation before running `supabase db push`.
4. Push to `main`. Render rebuilds the API Docker image and Vercel rebuilds the web app
   automatically.
5. Verify: `GET /health` on the production API returns OK (allow up to a minute for a
   cold start), the home page loads, and one data page renders.
6. If an ETL change shipped, trigger the ETL workflow manually for one event and confirm
   row counts look right.
7. Report what was deployed and the verification results. If anything failed, explain
   and suggest a rollback (redeploy the previous commit on Render/Vercel).

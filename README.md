# Oryne API

Backend for the Oryne Network dashboard: FastAPI + Supabase (Postgres and Auth), hosted on Render.
Architecture and phases: see `docs/BACKEND_PLAN.md` in the dashboard repo.

**Phase 1 (this release):** schema, auth and roles, merchants, domains, API keys, access requests, activity log.
No Daraja calls and no money movement yet.

## Local development

```bash
uv sync                                  # install (Python 3.12)
cp .env.example .env                     # leave DATABASE_URL unset to use local SQLite
uv run alembic upgrade head              # create tables
uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
uv run pytest                            # tests (SQLite, no network)
uv run ruff check .
```

## Supabase setup

1. Create a project (region close to Render, e.g. eu-central-1 for Frankfurt).
2. **Database URL:** Project Settings → Database → Connection string → **Session pooler** (port 5432). Put it in `DATABASE_URL`.
3. **Auth URL:** Project Settings → API → Project URL. Put it in `SUPABASE_URL`. Access tokens are verified with the project's JWKS. Only legacy projects need `SUPABASE_JWT_SECRET`.
4. Run the migration against Supabase: `uv run alembic upgrade head`. RLS is switched on for every table with no policies, so the public anon/authenticated keys cannot read the data. Only this API, connecting as the database owner, can.
5. Authentication → Users → **Add user** (your email and a password).
6. Give that user dashboard access:

   ```bash
   uv run python -m app.cli grant --email you@oryne.network --role super_admin --name "Your Name"
   ```

   Roles: `super_admin`, `ops`, `finance` (read-only), `merchant_owner`, `merchant_staff` (the last two need `--merchant ORY-M001`).

## Render

`render.yaml` is a Blueprint. In Render choose New → Blueprint, then pick this repo. Set the `sync: false` variables in the dashboard. The `API_KEY_PEPPER` is generated once and must **never** be changed afterwards. Migrations run as the pre-deploy step, and `/health` checks the database.

## Conventions

- Money is integer **cents** (KES × 100) everywhere, in the database and the API.
- Errors look like `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Merchant API keys look like `ory_sk_live_…` / `ory_pk_live_…`. The raw key is shown once and only an HMAC is stored. Publishable keys only work from the merchant's registered domains.

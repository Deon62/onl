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

## Supabase setup (SQL Editor)

1. Create a project. SQL Editor → paste and run **`supabase_schema.sql`** (once). It creates all tables with RLS on,
   so the public Supabase keys can't read anything; only this API can.
2. Authentication → Users → **Add user** (yourself).
3. Edit the email in **`supabase_make_admin.sql`** and run it, which makes you `super_admin`.

Later schema changes ship as Alembic migrations and run automatically on each Render deploy.

## Render

Only three environment variables:

| Key | Value |
|---|---|
| `DATABASE_URL` | Supabase → Connect → **Session pooler** string (with your DB password) |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `API_KEY_PEPPER` | 32+ random chars. Never change it after keys are issued |

Production mode is detected from Render's `RENDER` variable, the public URL from `RENDER_EXTERNAL_URL`, and the Python
version from `.python-version`. Add `ALLOWED_ORIGINS` once the dashboard is deployed. Use a paid instance, because the free tier
sleeps and would miss M-Pesa callbacks. Health check: `/health`.

## Conventions

- Money is integer **cents** (KES × 100) everywhere, in the database and the API.
- Errors look like `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Merchant API keys look like `ory_sk_live_…` / `ory_pk_live_…`. The raw key is shown once and only an HMAC is stored. Publishable keys only work from the merchant's registered domains.

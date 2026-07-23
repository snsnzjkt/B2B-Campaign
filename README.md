# B2B Lead Discovery & Outreach Platform

Automates B2B lead discovery, qualification, AI-personalized outreach, and
email campaign sending, with a CRM layer on top. See
`docs/superpowers/specs/2026-07-23-foundation-design.md` for the full
program design and sub-project roadmap.

This repository currently implements the **Foundation** sub-project: auth,
the core data model (organizations, users, companies, leads), and the
Docker dev environment that later sub-projects (lead discovery, AI
personalization, email campaigns, dashboard, CRM) build on.

## Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python dependency manager)
- [pnpm](https://pnpm.io/) and Node.js 20+

## Setup

1. Copy the environment template and fill in secrets:

   ```bash
   cp .env.example .env
   ```

   At minimum, set `SECRET_KEY` to a random string. `GOOGLE_CLIENT_ID` /
   `NEXT_PUBLIC_GOOGLE_CLIENT_ID` are only needed if you enable Google
   sign-in.

2. Start Postgres and Redis:

   ```bash
   docker compose up -d db redis
   ```

3. Install backend dependencies and run migrations:

   ```bash
   cd apps/api
   uv sync
   uv run alembic upgrade head
   ```

4. Install frontend dependencies:

   ```bash
   cd apps/web
   pnpm install
   ```

5. Run the full stack:

   ```bash
   docker compose up --build
   ```

   - API: http://localhost:8000 (interactive docs at `/docs`)
   - Web: http://localhost:3000

## Running tests

Backend (in-memory SQLite, no external services needed):

```bash
cd apps/api
uv run pytest -v
```

Frontend build/lint check:

```bash
cd apps/web
pnpm lint
pnpm build
```

Frontend end-to-end smoke test (requires the full stack running via
`docker compose up`):

```bash
cd apps/web
pnpm test:e2e
```

## Project structure

```
apps/
  api/   FastAPI backend (SQLAlchemy, Alembic, JWT + Google OAuth, REST API)
  web/   Next.js frontend (TypeScript, Tailwind, shadcn/ui)
docs/
  superpowers/specs/   Design specs, one per sub-project
  superpowers/plans/   Implementation plans, one per sub-project
```

## Compliance

Lead sourcing and email sending features (added in later sub-projects)
are required to respect target sites' robots.txt/ToS, maintain a
suppression list, honor unsubscribe/opt-out requests, and avoid
harvesting personal data from sources that prohibit automated access.
See the design spec for details.

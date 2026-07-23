# B2B Lead Discovery & Outreach Platform — Foundation Design

Status: Approved
Date: 2026-07-23

## Program context

The overall product is a web app that automates B2B lead discovery, qualification,
AI-personalized cold email generation, and campaign sending/tracking, with a CRM layer
on top. It is too large for a single spec, so it is decomposed into sub-projects, each
getting its own design doc and implementation plan:

1. **Foundation** (this doc) — monorepo, auth, core data model, Docker dev environment, CI.
2. **Lead Discovery & Import** — CSV import, provider-adapter interface, Google Places
   adapter, contact verification.
3. **AI Research & Personalization** — Playwright site crawl per lead, LLM company summary,
   lead scoring, personalized email generation.
4. **Email Campaign Engine** — SendGrid (default) + pluggable SES/Mailgun/Postmark adapters,
   scheduling, rate limiting, follow-up sequences, bounce/unsubscribe handling, suppression list.
5. **Dashboard & Analytics** — campaign stats (open/reply/bounce/click rates), template and
   AI-prompt management UI.
6. **CRM** — tags, notes, pipeline stages, CSV export, public API.

Sub-projects are built in this order because each depends on the previous one's data model.

### Cross-cutting decisions (apply to all sub-projects)

- **Backend**: FastAPI (Python), chosen over NestJS because it pairs naturally with
  Playwright-based site crawling and Python's AI tooling, keeping the scrape → research →
  personalize pipeline in one language.
- **LLM strategy**: pluggable provider interface prioritizing free/open-weight models.
  Default is a **local Ollama** adapter (fully free, no per-token cost). A **Groq** adapter
  (hosted open-weight models — Llama 3.x / Mixtral / Qwen — on Groq's free tier) is provided
  as an alternative for environments without a GPU. An OpenAI adapter may be added later
  behind the same interface but is not part of the initial build.
- **Email provider strategy**: pluggable adapter interface. **SendGrid** is the default/first
  adapter (perpetual 100 emails/day free tier, built-in bounce/unsubscribe webhooks, open/click
  tracking). SES, Mailgun, and Postmark are designed as adapters implementing the same
  interface, added in sub-project 4's implementation but not required for v1 to function.
- **Lead sourcing strategy**: CSV import is the always-free baseline. New-lead discovery goes
  through a pluggable provider-adapter interface hitting APIs that explicitly permit automated
  access (Google Places API as the default adapter). Playwright is used only to crawl a
  *known* lead's own company website (for AI research/personalization), never to scrape
  third-party directories or social networks whose ToS prohibit it (e.g. LinkedIn).
- **Deployment**: Docker Compose (self-hosted, no required cloud spend) containing Postgres,
  Redis, the FastAPI API, a Celery worker (provisioned in sub-project 4), and the Next.js web
  app.
- **Compliance**: every sourcing/sending feature in every sub-project must respect
  robots.txt/ToS on crawl targets, maintain a suppression list, honor unsubscribe/opt-out, and
  avoid harvesting personal emails from prohibited sources. This is a hard constraint on
  sub-projects 2–4, not a separate feature.

## This sub-project: Foundation

### Goal

Stand up the monorepo, dev environment, auth, and the minimal data model (Organization,
User, Company, Lead) that every later sub-project builds on.

### Architecture

```
b2b-campaign/
  apps/
    web/          Next.js 15 App Router, TypeScript, Tailwind + shadcn/ui
    api/          FastAPI, SQLAlchemy 2.0, Alembic migrations
  infra/
    docker/       Dockerfiles + docker-compose.yml (postgres, redis, api, web)
  docs/
```

No shared code package across the language boundary. The frontend consumes the API via a
client generated from FastAPI's OpenAPI schema, so request/response types stay in sync
without hand-maintained duplication.

- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic; `uv` for Python dependency management;
  `pytest` for tests.
- **Frontend**: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui; `pnpm`. Visual
  direction: clean, warm-neutral palette, generous whitespace, restrained single accent
  color — a calm, professional look rather than a dense enterprise-SaaS dashboard.
- **Auth**: JWT (short-lived access token + refresh token) issued by the API, plus Google
  OAuth. Passwords hashed with bcrypt via `passlib`.
- **Multi-tenancy**: one `Organization` per account, with `User`s (role: owner/member)
  belonging to exactly one org. Every domain table is scoped by `organization_id`.

### Data model (this sub-project only)

- `Organization(id, name, created_at)`
- `User(id, org_id, email, hashed_password, oauth_provider, oauth_id, role, created_at)`
- `Company(id, org_id, name, website, industry, size_range, location, description,
  social_links jsonb, source, created_at)`
- `Lead(id, org_id, company_id, contact_name, job_title, email, phone, email_verified,
  score, status, created_at)`

Campaign, Template, AI-prompt, suppression-list, email-event, note, and pipeline-stage
tables are deliberately deferred to the sub-projects that use them (2–6), rather than
speculatively designed now.

### Scope delivered

- Docker Compose stack: Postgres, Redis (provisioned now, consumed by sub-project 4's
  Celery workers later), API, Web.
- Auth flows: register/login (email+password), Google OAuth, JWT refresh, protected routes,
  logout.
- Company + Lead: SQLAlchemy models, Alembic migration, REST CRUD endpoints, OpenAPI docs
  served at `/docs`.
- Minimal dashboard shell: login/register pages, top nav, an empty-state Leads list page
  wired to the real API (no discovery/scoring yet — that is sub-project 2).
- Testing: pytest (unit tests + one integration test against a test database) for the API;
  a smoke test for the web app.
- CI: GitHub Actions workflow running lint + tests for both apps on push.
- `.env.example` and a README covering setup, configuration, and running the stack locally.

### Error handling

FastAPI exception handlers return a consistent JSON error shape: `{code, message, details}`.
The frontend has a shared API-error boundary/toast that reads this shape. Auth failures
return 401 with a machine-readable reason so the frontend can distinguish "expired token"
(triggers a silent refresh) from "invalid credentials" (shows an inline error).

### Testing strategy

- API: pytest with a disposable Postgres test database (via testcontainers or a
  docker-compose test service); unit tests for auth/password/JWT logic; integration tests
  for the Company/Lead CRUD endpoints.
- Web: component smoke tests plus a minimal Playwright test that logs in and loads the
  leads page, to catch integration breaks between frontend and API early.

### Out of scope (explicitly deferred to later sub-projects)

- Lead discovery/import, scoring, AI research/personalization, email sending, analytics,
  CRM features (tags/notes/pipeline/export), and any Playwright crawling.

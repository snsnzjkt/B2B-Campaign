# Lead Discovery & Import — Design

Status: Approved
Date: 2026-07-24

## Program context

This is sub-project 2 of the B2B lead-discovery/outreach platform (see
`docs/superpowers/specs/2026-07-23-foundation-design.md` for the full 6-sub-project roadmap
and cross-cutting decisions binding on all of them: pluggable-adapter strategy for
LLM/email/discovery providers, multi-tenancy via `organization_id` scoping on every table,
the `_get_<resource>_or_404` convention, `{code, message, details}` error shape, and
compliance guardrails on sourcing/crawling).

**Scope change from the original roadmap:** the Foundation spec listed this sub-project as
"CSV import, provider-adapter interface, Google Places adapter, contact verification." After
discussion, CSV import is dropped — the user wants leads sourced exclusively through
discovery (Google Places), not manual file upload. This sub-project is now
**discovery-only**: a pluggable lead-discovery-provider interface, a Google Places adapter,
and email verification (applied wherever a lead gets an email, now or later).

Google Places API returns business info (name, address, phone, website), not personal
contacts. Leads created via discovery have empty contact fields (`contact_name`, `email`,
`job_title` all null); populating those is sub-project 3's job (AI research via per-company
site crawl). "Contact verification" in this sub-project therefore means: whenever a lead's
`email` is set or changed (via the existing `leads` endpoints, by a human now or by
sub-project 3 later), validate format + MX record and set `email_verified` accordingly. It
is not a discovery-time feature since discovery doesn't produce emails.

## Goal

Let a user search for companies via Google Places, review results, and select which ones to
import as `Company` + bare `Lead` records — without creating duplicates and without runaway
API cost.

## Architecture

```
apps/api/app/
  providers/
    __init__.py
    base.py              # LeadDiscoveryProvider ABC
    google_places.py     # GooglePlacesProvider
  core/
    email_verify.py      # verify_email(email) -> bool
  api/routes/
    discovery.py          # POST /discovery/search, POST /discovery/import
  models/
    company.py            # + external_id column
    provider_search_log.py  # new
apps/web/app/(dashboard)/leads/discover/
  page.tsx                # search form + results table + import action
```

`LeadDiscoveryProvider` is an abstract base with a single method:

```python
class LeadDiscoveryProvider(ABC):
    @abstractmethod
    def search(self, query: str, location: str) -> list[DiscoveredCompany]: ...
```

`DiscoveredCompany` is a small dataclass: `name, website, phone, address, external_id`. This
mirrors the pluggable-provider pattern already decided for LLM and email adapters, so a
second discovery provider can be added later behind the same interface without touching
routes.

## Data model changes

- `Company.external_id: str | None`, indexed — the provider's place ID, used for dedup
  matching on re-search.
- New table `ProviderSearchLog(id, organization_id, provider, created_at)` — one row per
  search call. Used only to count searches in the current calendar month against the cap;
  no query/location text is stored (avoids retaining search terms beyond what's needed).

Both delivered via a new Alembic migration, following the existing one-migration-per-table-
change convention.

## Config additions

`app/config.py`:
- `google_places_api_key: str = ""`
- `discovery_search_monthly_cap: int = 200`

## Discovery flow

1. **Search** — `POST /discovery/search {query, location}`
   - Counts the org's `ProviderSearchLog` rows for the current calendar month; if
     `>= discovery_search_monthly_cap`, raises `RateLimitExceededError` (429) before calling
     the provider.
   - Otherwise logs the search (insert `ProviderSearchLog` row), calls
     `GooglePlacesProvider.search(query, location)`.
   - For each result, checks whether a `Company` already exists in the org matching on
     `external_id` (place ID) or normalized website domain, and annotates
     `already_imported: bool`.
   - Returns candidates directly in the response — **not persisted**. Response item shape:
     `{name, address, website, phone, external_id, already_imported}`.

2. **Review** — frontend renders results in a table; rows with `already_imported: true` show
   a disabled, checked-off state so the user can see them but not re-select them.

3. **Import** — `POST /discovery/import {candidates: [...]}`
   - Client sends back the full candidate objects the user selected (no server-side
     search-result cache — keeps search stateless).
   - For each candidate, re-checks dedup server-side (defensive against a stale client-side
     list), skipping any that now match an existing `Company`.
   - For the rest: creates `Company(source="google_places", external_id=..., name=...,
     website=..., ...)` and a bare `Lead(company_id=..., status="new")` with all contact
     fields null.
   - Returns `{created: N, skipped_duplicate: N}`.

All endpoints require auth (`get_current_user`) and are org-scoped like every other route.

## Email verification

`app/core/email_verify.py`:

```python
def verify_email(email: str) -> bool: ...
```

Validates format (Pydantic `EmailStr`-equivalent), then performs an MX-record DNS lookup on
the domain via `dnspython` (new dependency — remember to regenerate/commit `uv.lock`
alongside the `pyproject.toml` change). Returns `False` on malformed address or no MX record,
`True` otherwise. No third-party verification API (ZeroBounce/NeverBounce) — consistent with
the project's free-tooling preference; this is the ceiling of what we check.

This is wired into the **existing** `leads.py` `create_lead` / `update_lead` handlers: any
request that sets or changes `email` triggers `verify_email()` and sets `email_verified`
from its result, instead of `email_verified` staying permanently `False`. This means
sub-project 3, when it later sets lead emails after site-crawl research through the same
`PATCH /leads/{id}` endpoint, gets verification for free with no new work.

## Error handling

One new `AppError` subclass in `app/core/errors.py`:

```python
class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Monthly search limit reached"):
        super().__init__(code="rate_limit_exceeded", message=message, status_code=429)
```

All other errors reuse the existing `{code, message, details}` shape and subclasses.

## Testing strategy

- **Provider layer**: unit tests for `GooglePlacesProvider` with HTTP mocked via `respx`
  (new dev dependency) — no real API key or network access needed to run the suite.
- **Discovery routes**: pytest integration tests against the test DB covering:
  - cap enforcement (search rejected with 429 once the monthly count is at/over the cap)
  - dedup marking on search (`already_imported` true for a place ID or website already in
    the org, false otherwise)
  - import dedup re-check (stale client list still skips already-existing companies)
  - org-scoping (one org's searches/imports never see/affect another org's data)
- **Email verification**: unit tests for `verify_email()` with DNS resolution mocked (valid
  MX, no MX, malformed address), plus an integration test that `PATCH /leads/{id}` with a new
  email updates `email_verified` accordingly.
- **Frontend**: component-level test for the discover page (search renders results, already-
  imported rows are disabled, selecting + importing shows the created/skipped summary), API
  calls mocked. Not extending the Playwright e2e smoke test in this sub-project — mocking
  Google Places at the e2e layer isn't worth the complexity yet; the logic that matters here
  is covered at the component/integration level.

## Out of scope (explicitly deferred)

- CSV import — dropped from this sub-project entirely (see Scope change note above).
- Personal-contact discovery/enrichment (contact name, email, job title) — sub-project 3.
- Third-party email-verification APIs — MX-check only.
- Additional discovery providers beyond Google Places — interface supports them, none
  implemented now.
- Any Playwright/site-crawling — still sub-project 3.

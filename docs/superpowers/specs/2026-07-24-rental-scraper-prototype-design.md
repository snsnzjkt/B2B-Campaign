# Rental Scraper Campaign Prototype — Design

Status: Approved
Date: 2026-07-24

## Program context

This is a **client-requested, out-of-band prototype** — not a numbered sub-project in the
main roadmap (see `docs/superpowers/specs/2026-07-23-foundation-design.md`). It deliberately
jumps ahead of sub-project 3 (AI Research & Personalization) and sub-project 4 (Email
Campaign Engine), neither of which has started, to give the client a working end-to-end demo
(scrape → review → import → send) on a short timeline.

It also deliberately deviates from a documented cross-cutting guardrail: the Foundation spec
states Playwright crawling is "only ever used against a lead's own company website... never
to scrape third-party directories or social networks whose ToS prohibits it." The client
specifically wants leads sourced from Airbnb, VRBO, and Booking.com listings. **The client has
been informed** that scraping these platforms violates their Terms of Service, that all three
run active bot-detection and may block or CAPTCHA-wall requests, and that this code is not
intended to run at production scale or survive long-term without maintenance. This spec
proceeds on that basis, scoped explicitly as disposable prototype code.

This work does not change or replace the in-progress sub-project 2 (Lead Discovery & Import
via Google Places) — that continues on its own track. This prototype is additive and isolated.

## Goal

Give the client a clickable demo: pick a platform (Airbnb/VRBO/Booking.com), scrape listings
for a query + location, see guessed/verified contact emails, import selected results as real
leads, and send a single templated outreach email to the ones with a verified address — all
from a page in the existing dashboard.

## Non-goals

- Reliable, maintained, production-grade scraping. If a platform blocks the request, we
  report it and move on.
- Any of sub-project 3 (AI personalization) or sub-project 4 (real campaign engine: sequences,
  scheduling, bounce handling, suppression lists) scope. Fixed single template, one-shot send.
- High email hit rate. Airbnb/VRBO/Booking.com don't expose contact emails; guessing from a
  domain search is best-effort.

## Architecture

```
apps/api/app/prototype_scraper/
  __init__.py
  scrapers/
    base.py           # ScrapedListing dataclass: platform, host_name, listing_title,
                       #   listing_url, location
    airbnb.py          # scrape_airbnb(query, location) -> list[ScrapedListing]
    vrbo.py             # scrape_vrbo(query, location) -> list[ScrapedListing]
    booking.py          # scrape_booking(query, location) -> list[ScrapedListing]
  email_guess.py        # guess_domain(host_name), guess_emails(domain) -> candidates,
                         #   verified via app.core.email_verify.verify_email
  routes.py              # POST /prototype/scrape, POST /prototype/import,
                          #   POST /prototype/send-campaign
apps/web/app/(dashboard)/leads/scrape/
  page.tsx                # platform picker + query/location form, results table,
                           #   select+import, send button
```

Deliberately walled off under `prototype_scraper/` and the `/prototype` route prefix — one
folder to delete, or to mine for reference, when sub-projects 3/4 are built for real. Does
**not** use the pluggable-provider interface pattern the rest of the roadmap follows; each
platform gets its own scraper function since markup differs completely and a shared
abstraction isn't worth it for disposable code.

No new DB tables or migrations. Reuses `Company` (`source` is already a free-text
`String(50)` — scraped rows use `source="scraper_airbnb"` / `"scraper_vrbo"` /
`"scraper_booking"`) and `Lead` (existing `email`, `email_verified`, `status` fields).

## New dependencies

- `playwright` (backend) — headless Chromium for JS-rendered listing pages. Already
  anticipated as a future dependency for sub-project 3.
- No new dependency for email: reuses `requests` (already present) both for a lightweight
  DuckDuckGo HTML search (domain guessing, no paid search API) and for calling SendGrid's
  `/v3/mail/send` HTTP endpoint directly (no `sendgrid` SDK needed for one call type).

## Config additions

`app/config.py`:
- `sendgrid_api_key: str = ""`
- `sendgrid_from_email: str = ""`

## Flow

1. **Scrape** — `POST /prototype/scrape {platform, query, location}`
   - Launches headless Chromium via Playwright, navigates the platform's search results,
     parses listing cards into `ScrapedListing` rows.
   - Per-listing, not per-run: if a platform blocks the request (CAPTCHA, 403, empty DOM),
     that platform's scrape returns an empty list plus a warning string (e.g.
     `"blocked_or_no_results"`) instead of raising — the caller can still get results from
     the other platforms in the same UI session.
   - Nothing persisted yet (mirrors sub-project 2's discovery-search pattern).

2. **Email guess** — run inline per scraped candidate before the response is returned:
   - `guess_domain(host_name)`: DuckDuckGo HTML search for the host/listing name; take the
     first result domain that isn't the platform itself or a known directory site.
   - `guess_emails(domain)`: try `info@`, `contact@`, `hello@` in that order.
   - Each candidate run through the existing `verify_email()` MX check; first pass wins. No
     match → candidate returned with `guessed_email: null`.
   - Response item: `{platform, host_name, listing_title, listing_url, location,
     guessed_email, email_verified}`.

3. **Review** — results table on the new page. Rows without a verified email are visually
   flagged (muted, not disabled) — still selectable for import (creates a lead for manual
   follow-up later) but excluded from the send step.

4. **Import** — `POST /prototype/import {candidates: [...]}` — client resends the full
   candidate objects it wants imported (stateless search, same convention as sub-project 2).
   For each: creates `Company(source="scraper_<platform>", name=host_name,
   website=listing_url, location=location)` + `Lead(email=guessed_email,
   email_verified=..., status="new")`. No dedup logic — out of scope for this prototype
   (acceptable since it's a one-off bounded demo run, not a standing feature).

5. **Send campaign** — `POST /prototype/send-campaign {lead_ids: [...]}`
   - Fixed, hardcoded template (subject + body) with `{business_name}` / `{location}`
     substitution — no template management UI.
   - Only sends to leads with `email_verified=True` and `status="new"`.
   - One synchronous `requests.post` per lead to SendGrid's `/v3/mail/send`; on success sets
     `status="contacted"`. No retry, queue, or scheduling.

All routes require auth (`get_current_user`) and are org-scoped like every other route,
consistent with the multi-tenancy rule even though this is prototype code.

## Error handling

- Scrape: failures are per-platform and non-fatal to the overall request (see Flow step 1).
- Email guess: no domain found or no email passes MX → `guessed_email: null`, surfaced in the
  UI, not an error.
- Send: a SendGrid failure for one lead is caught and reported per-lead in the response
  (`{sent: N, failed: [{lead_id, error}]}`); does not abort the rest of the batch.

## Testing strategy

Deliberately light, consistent with this being disposable prototype code:
- Unit tests for `email_guess.py` (pattern generation, MX-check reuse) — deterministic, no
  network needed (MX check mocked as it already is in sub-project 2's tests).
- No tests for the scraper modules themselves — they depend on live third-party DOM structure
  that will drift out from under any fixture; a passing test today says nothing about
  tomorrow. Verified manually against the real sites before the client demo.
- No e2e test for the new page, same reasoning sub-project 2 used for skipping e2e on the
  discovery page (mocking three hostile external sites isn't worth the complexity here).

## Out of scope (explicitly deferred)

- Follow-up sequences, scheduling, bounce/unsubscribe handling, suppression lists — real
  sub-project 4 scope.
- AI-personalized email copy — sub-project 3 scope. Fixed template only.
- Resilience to site layout changes, proxy rotation, CAPTCHA-solving, or any anti-detection
  engineering — if blocked, we report and move on.
- Search/monthly rate-limit caps like sub-project 2 — not needed for a bounded demo run.
- Dedup on re-scrape/re-import — acceptable gap for a one-off prototype.
- Long-term maintenance of this code path — expected to be deleted or fully rewritten when
  sub-projects 3 and 4 are built properly.

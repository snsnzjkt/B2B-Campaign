# Lead Discovery & Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user search Google Places for companies, review results, and select which ones to import as `Company` + bare `Lead` records, with dedup and a monthly search cap; plus wire MX-based email verification into the existing Lead endpoints.

**Architecture:** A new `app/providers/` package holds a `LeadDiscoveryProvider` interface and a `GooglePlacesProvider` implementation. Two new stateless routes (`POST /discovery/search`, `POST /discovery/import`) drive a search→review→import flow from a new frontend page. A small `app/core/dedup.py` module normalizes websites and finds duplicate companies, reused by both routes. `app/core/email_verify.py` does format + MX-record checks and is wired into the *existing* `leads.py` create/update handlers so any lead that gets an email — now or from a future sub-project — gets verified automatically.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + `uv` (backend), Next.js App Router + TypeScript + Tailwind + shadcn/ui + `pnpm` (frontend). New deps: `dnspython` (backend, MX lookups), shadcn `checkbox` component (frontend).

## Global Constraints

- Every domain table has `organization_id` and every query filters on it (multi-tenancy).
- Reuse the `_get_<resource>_or_404` / org-ownership-check convention already used in `companies.py`/`leads.py` for any new resource lookups.
- All API errors return `{code, message, details}` via `AppError` subclasses (see `app/core/errors.py`).
- If a Python dependency changes in `apps/api/pyproject.toml`, regenerate and commit `apps/api/uv.lock` in the same commit — use `uv add <package>` so this happens atomically. Same for `apps/web/pnpm-lock.yaml` when a frontend dependency changes.
- Compliance: discovery only calls an API that explicitly permits automated access (Google Places). No scraping of third-party directories/social networks.
- CSV import is explicitly out of scope for this sub-project (dropped per updated direction — see design spec's "Scope change" note).
- Design spec: `docs/superpowers/specs/2026-07-24-lead-discovery-import-design.md` — read it if any task instruction here seems ambiguous.

---

### Task 1: Data model — `Company.external_id` + `ProviderSearchLog`

**Files:**
- Modify: `apps/api/app/models/company.py`
- Create: `apps/api/app/models/provider_search_log.py`
- Modify: `apps/api/app/models/__init__.py`
- Modify: `apps/api/app/schemas/company.py`
- Create: `apps/api/alembic/versions/f3a6b9c1d0e2_add_company_external_id_and_provider_.py`
- Modify: `apps/api/app/tests/test_models.py`

**Interfaces:**
- Produces: `Company.external_id: str | None` column; `ProviderSearchLog(id, organization_id, provider, created_at)` model, importable as `from app.models import ProviderSearchLog`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `apps/api/app/tests/test_models.py` with:

```python
from app.models import Company, Organization, ProviderSearchLog, User


def test_create_organization_and_user(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    user = User(organization_id=org.id, email="founder@acme.com", hashed_password="hashed", role="owner")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.get(User, user.id)
    assert fetched is not None
    assert fetched.organization.name == "Acme Inc"


def test_company_external_id_persists(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    company = Company(organization_id=org.id, name="Acme Corp", external_id="place-123")
    db_session.add(company)
    db_session.commit()

    fetched = db_session.get(Company, company.id)
    assert fetched.external_id == "place-123"


def test_provider_search_log_persists(db_session):
    org = Organization(name="Acme Inc")
    db_session.add(org)
    db_session.flush()

    log = ProviderSearchLog(organization_id=org.id, provider="google_places")
    db_session.add(log)
    db_session.commit()

    fetched = db_session.get(ProviderSearchLog, log.id)
    assert fetched.provider == "google_places"
    assert fetched.created_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `apps/api`): `uv run pytest app/tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProviderSearchLog'` (and `Company(...)` rejecting `external_id` as an unexpected kwarg).

- [ ] **Step 3: Add `external_id` to the `Company` model**

In `apps/api/app/models/company.py`, change:

```python
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

to:

```python
    source: Mapped[str] = mapped_column(String(50), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Create the `ProviderSearchLog` model**

Create `apps/api/app/models/provider_search_log.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProviderSearchLog(Base):
    __tablename__ = "provider_search_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Export it from `app/models/__init__.py`**

Replace the full contents of `apps/api/app/models/__init__.py` with:

```python
from app.models.company import Company
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.provider_search_log import ProviderSearchLog
from app.models.user import User

__all__ = ["Company", "Lead", "Organization", "ProviderSearchLog", "User"]
```

- [ ] **Step 6: Add `external_id` to `CompanyResponse`**

In `apps/api/app/schemas/company.py`, change:

```python
    social_links: dict
    source: str
    created_at: datetime
```

to:

```python
    social_links: dict
    source: str
    external_id: str | None
    created_at: datetime
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Add the Alembic migration**

Create `apps/api/alembic/versions/f3a6b9c1d0e2_add_company_external_id_and_provider_.py`:

```python
"""add company external_id and provider_search_logs table

Revision ID: f3a6b9c1d0e2
Revises: 02ef149f3566
Create Date: 2026-07-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a6b9c1d0e2'
down_revision: Union[str, Sequence[str], None] = '02ef149f3566'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('companies', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_companies_external_id'), 'companies', ['external_id'], unique=False)

    op.create_table('provider_search_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_search_logs_organization_id'), 'provider_search_logs', ['organization_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_provider_search_logs_organization_id'), table_name='provider_search_logs')
    op.drop_table('provider_search_logs')

    op.drop_index(op.f('ix_companies_external_id'), table_name='companies')
    op.drop_column('companies', 'external_id')
```

If a local Postgres is running (`docker compose up -d postgres` from the repo root), verify it applies cleanly: `uv run alembic upgrade head` from `apps/api`, expect no errors. If no local Postgres is available, skip this verification — pytest doesn't depend on the migration (it builds tables from the models directly).

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/models/company.py apps/api/app/models/provider_search_log.py apps/api/app/models/__init__.py apps/api/app/schemas/company.py apps/api/app/tests/test_models.py apps/api/alembic/versions/f3a6b9c1d0e2_add_company_external_id_and_provider_.py
git commit -m "feat(api): add Company.external_id and ProviderSearchLog for discovery dedup/rate-limiting"
```

---

### Task 2: Dedup helpers — `normalize_website` + `find_duplicate_company`

**Files:**
- Create: `apps/api/app/core/dedup.py`
- Create: `apps/api/app/tests/test_dedup.py`

**Interfaces:**
- Consumes: `Company` model with `external_id`, `website`, `organization_id` (Task 1).
- Produces: `normalize_website(website: str | None) -> str | None`; `find_duplicate_company(db: Session, organization_id: uuid.UUID, external_id: str, website: str | None) -> Company | None`. Both imported later as `from app.core.dedup import find_duplicate_company, normalize_website`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/app/tests/test_dedup.py`:

```python
import uuid

from app.core.dedup import find_duplicate_company, normalize_website
from app.models import Company


def test_normalize_website_strips_scheme_and_www():
    assert normalize_website("https://www.Acme.com/path") == "acme.com"


def test_normalize_website_handles_bare_domain():
    assert normalize_website("acme.com") == "acme.com"


def test_normalize_website_none_and_empty():
    assert normalize_website(None) is None
    assert normalize_website("") is None


def test_find_duplicate_company_by_external_id(db_session):
    org_id = uuid.uuid4()
    db_session.add(Company(organization_id=org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "place-1", None)
    assert match is not None
    assert match.name == "Acme"


def test_find_duplicate_company_by_normalized_website(db_session):
    org_id = uuid.uuid4()
    db_session.add(
        Company(organization_id=org_id, name="Acme", website="https://www.acme.com", external_id="place-1")
    )
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "different-place-id", "http://acme.com/")
    assert match is not None


def test_find_duplicate_company_no_match(db_session):
    org_id = uuid.uuid4()
    db_session.add(Company(organization_id=org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, org_id, "place-2", "https://other.com")
    assert match is None


def test_find_duplicate_company_scoped_to_organization(db_session):
    other_org_id = uuid.uuid4()
    db_session.add(Company(organization_id=other_org_id, name="Acme", external_id="place-1"))
    db_session.commit()

    match = find_duplicate_company(db_session, uuid.uuid4(), "place-1", None)
    assert match is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.dedup'`

- [ ] **Step 3: Implement `app/core/dedup.py`**

```python
import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company


def normalize_website(website: str | None) -> str | None:
    if not website:
        return None
    parsed = urlparse(website if "://" in website else f"//{website}")
    host = (parsed.netloc or parsed.path).lower()
    return host[4:] if host.startswith("www.") else host


def find_duplicate_company(
    db: Session, organization_id: uuid.UUID, external_id: str, website: str | None
) -> Company | None:
    normalized = normalize_website(website)
    companies = db.scalars(select(Company).where(Company.organization_id == organization_id)).all()
    for company in companies:
        if company.external_id == external_id:
            return company
        if normalized and normalize_website(company.website) == normalized:
            return company
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_dedup.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/dedup.py apps/api/app/tests/test_dedup.py
git commit -m "feat(api): add website-normalization and company dedup helpers"
```

---

### Task 3: Email verification — `verify_email`

**Files:**
- Modify: `apps/api/pyproject.toml` (+ `apps/api/uv.lock`, regenerated)
- Create: `apps/api/app/core/email_verify.py`
- Create: `apps/api/app/tests/test_email_verify.py`

**Interfaces:**
- Produces: `verify_email(email: str) -> bool`, imported later as `from app.core.email_verify import verify_email`.

- [ ] **Step 1: Add the `dnspython` dependency**

From `apps/api`, run: `uv add dnspython`
This updates `pyproject.toml` and regenerates `uv.lock` together.

- [ ] **Step 2: Write the failing tests**

Create `apps/api/app/tests/test_email_verify.py`:

```python
from unittest.mock import patch

import dns.exception

from app.core.email_verify import verify_email


def test_verify_email_valid_with_mx():
    with patch("app.core.email_verify.dns.resolver.resolve", return_value=["mx1.example.com"]):
        assert verify_email("person@example.com") is True


def test_verify_email_no_mx_record():
    with patch("app.core.email_verify.dns.resolver.resolve", side_effect=dns.exception.DNSException()):
        assert verify_email("person@example.com") is False


def test_verify_email_malformed_address():
    assert verify_email("not-an-email") is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_email_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.email_verify'`

- [ ] **Step 4: Implement `app/core/email_verify.py`**

```python
import dns.exception
import dns.resolver
from email_validator import EmailNotValidError, validate_email


def verify_email(email: str) -> bool:
    try:
        valid = validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return False

    try:
        dns.resolver.resolve(valid.domain, "MX")
    except dns.exception.DNSException:
        return False
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_email_verify.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/core/email_verify.py apps/api/app/tests/test_email_verify.py
git commit -m "feat(api): add MX-record email verification helper"
```

---

### Task 4: Wire email verification into Lead create/update

**Files:**
- Modify: `apps/api/app/api/routes/leads.py`
- Modify: `apps/api/app/tests/test_leads.py`

**Interfaces:**
- Consumes: `verify_email(email: str) -> bool` (Task 3).

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/app/tests/test_leads.py` (add the import at the top and the two tests at the end):

Add to the top of the file:
```python
from unittest.mock import patch
```

Add at the end of the file:
```python
def test_create_lead_with_email_sets_verified_from_check(client, auth_headers):
    with patch("app.api.routes.leads.verify_email", return_value=True):
        response = client.post(
            "/api/v1/leads",
            json={"contact_name": "Jane Doe", "email": "jane@example.com"},
            headers=auth_headers,
        )
    assert response.status_code == 201
    assert response.json()["email_verified"] is True


def test_update_lead_email_reverifies(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    with patch("app.api.routes.leads.verify_email", return_value=False):
        response = client.patch(
            f"/api/v1/leads/{lead_id}", json={"email": "bad@nomx.example"}, headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_leads.py -v -k "email"`
Expected: FAIL — both assert `email_verified is True`/`is False` against the current default of `False` (create) or the update handler not touching it at all (`email_verified` stays whatever it was).

- [ ] **Step 3: Wire verification into `leads.py`**

In `apps/api/app/api/routes/leads.py`, add the import:

```python
from app.core.email_verify import verify_email
```

Change `create_lead` from:

```python
@router.post("", response_model=LeadResponse, status_code=201)
def create_lead(
    payload: LeadCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _validate_company(db, current_user, payload.company_id)
    lead = Lead(organization_id=current_user.organization_id, **payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
```

to:

```python
@router.post("", response_model=LeadResponse, status_code=201)
def create_lead(
    payload: LeadCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _validate_company(db, current_user, payload.company_id)
    lead = Lead(organization_id=current_user.organization_id, **payload.model_dump())
    if lead.email:
        lead.email_verified = verify_email(lead.email)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
```

Change `update_lead` from:

```python
@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = _get_lead_or_404(db, current_user, lead_id)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        _validate_company(db, current_user, data["company_id"])
    for field, value in data.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead
```

to:

```python
@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = _get_lead_or_404(db, current_user, lead_id)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data:
        _validate_company(db, current_user, data["company_id"])
    for field, value in data.items():
        setattr(lead, field, value)
    if "email" in data:
        lead.email_verified = verify_email(lead.email) if lead.email else False
    db.commit()
    db.refresh(lead)
    return lead
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_leads.py -v`
Expected: PASS (all tests in the file, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/api/routes/leads.py apps/api/app/tests/test_leads.py
git commit -m "feat(api): verify lead email on create/update via MX check"
```

---

### Task 5: `LeadDiscoveryProvider` interface + `GooglePlacesProvider`

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `.env.example`
- Create: `apps/api/app/providers/__init__.py`
- Create: `apps/api/app/providers/base.py`
- Create: `apps/api/app/providers/google_places.py`
- Create: `apps/api/app/tests/test_google_places_provider.py`

**Interfaces:**
- Produces: `DiscoveredCompany(name, website, phone, address, external_id)` dataclass; `LeadDiscoveryProvider` ABC with `search(query: str, location: str) -> list[DiscoveredCompany]`; `GooglePlacesProvider` implementing it. Imported later as `from app.providers.google_places import GooglePlacesProvider` and `from app.providers.base import DiscoveredCompany`.
- Consumes: `settings.google_places_api_key` (added this task).

- [ ] **Step 1: Add config**

In `apps/api/app/config.py`, change:

```python
    google_client_id: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
```

to:

```python
    google_client_id: str = ""
    google_places_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
```

In `.env.example`, add a line after `GOOGLE_CLIENT_ID=`:

```
GOOGLE_PLACES_API_KEY=
```

- [ ] **Step 2: Write the failing tests**

Create `apps/api/app/tests/test_google_places_provider.py`:

```python
from unittest.mock import Mock, patch

from app.providers.google_places import GooglePlacesProvider

FAKE_RESPONSE = {
    "places": [
        {
            "id": "place-123",
            "displayName": {"text": "Acme Corp"},
            "formattedAddress": "123 Main St, Denver, CO",
            "websiteUri": "https://acme.com",
            "internationalPhoneNumber": "+1 303-555-0100",
        }
    ]
}


def test_search_maps_places_response_to_discovered_companies():
    mock_response = Mock()
    mock_response.json.return_value = FAKE_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response) as mock_post:
        results = GooglePlacesProvider().search("marketing agencies", "Denver, CO")

    assert len(results) == 1
    assert results[0].name == "Acme Corp"
    assert results[0].website == "https://acme.com"
    assert results[0].phone == "+1 303-555-0100"
    assert results[0].address == "123 Main St, Denver, CO"
    assert results[0].external_id == "place-123"
    mock_post.assert_called_once()


def test_search_handles_missing_optional_fields():
    mock_response = Mock()
    mock_response.json.return_value = {
        "places": [{"id": "place-456", "displayName": {"text": "No Site LLC"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response):
        results = GooglePlacesProvider().search("agencies", "Denver, CO")

    assert results[0].website is None
    assert results[0].phone is None
    assert results[0].address is None


def test_search_empty_results():
    mock_response = Mock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status.return_value = None

    with patch("app.providers.google_places.requests.post", return_value=mock_response):
        results = GooglePlacesProvider().search("agencies", "Nowhere")

    assert results == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_google_places_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.providers'`

- [ ] **Step 4: Implement the provider package**

Create `apps/api/app/providers/__init__.py` (empty file).

Create `apps/api/app/providers/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DiscoveredCompany:
    name: str
    website: str | None
    phone: str | None
    address: str | None
    external_id: str


class LeadDiscoveryProvider(ABC):
    @abstractmethod
    def search(self, query: str, location: str) -> list[DiscoveredCompany]: ...
```

Create `apps/api/app/providers/google_places.py`:

```python
import requests

from app.config import settings
from app.providers.base import DiscoveredCompany, LeadDiscoveryProvider

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.internationalPhoneNumber"
)


class GooglePlacesProvider(LeadDiscoveryProvider):
    def search(self, query: str, location: str) -> list[DiscoveredCompany]:
        response = requests.post(
            PLACES_SEARCH_URL,
            json={"textQuery": f"{query} in {location}"},
            headers={
                "X-Goog-Api-Key": settings.google_places_api_key,
                "X-Goog-FieldMask": FIELD_MASK,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return [
            DiscoveredCompany(
                name=place.get("displayName", {}).get("text", ""),
                website=place.get("websiteUri"),
                phone=place.get("internationalPhoneNumber"),
                address=place.get("formattedAddress"),
                external_id=place["id"],
            )
            for place in data.get("places", [])
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_google_places_provider.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/config.py .env.example apps/api/app/providers apps/api/app/tests/test_google_places_provider.py
git commit -m "feat(api): add pluggable discovery-provider interface and Google Places adapter"
```

---

### Task 6: Discovery search endpoint

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `.env.example`
- Modify: `apps/api/app/core/errors.py`
- Create: `apps/api/app/schemas/discovery.py`
- Create: `apps/api/app/api/routes/discovery.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/app/tests/test_discovery_search.py`

**Interfaces:**
- Consumes: `find_duplicate_company` (Task 2), `GooglePlacesProvider` + `DiscoveredCompany` (Task 5), `ProviderSearchLog` (Task 1).
- Produces: `POST /api/v1/discovery/search`; `DiscoveryCandidate`, `DiscoverySearchRequest`, `DiscoverySearchResponse` schemas (extended by Task 7); `RateLimitExceededError`.

- [ ] **Step 1: Add config + error class**

In `apps/api/app/config.py`, change:

```python
    google_places_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
```

to:

```python
    google_places_api_key: str = ""
    discovery_search_monthly_cap: int = 200
    cors_origins: list[str] = ["http://localhost:3000"]
```

In `.env.example`, add a line after `GOOGLE_PLACES_API_KEY=`:

```
DISCOVERY_SEARCH_MONTHLY_CAP=200
```

In `apps/api/app/core/errors.py`, add at the end of the file:

```python
class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Monthly search limit reached"):
        super().__init__(code="rate_limit_exceeded", message=message, status_code=429)
```

- [ ] **Step 2: Write the failing tests**

Create `apps/api/app/tests/test_discovery_search.py`:

```python
from unittest.mock import patch

from app.providers.base import DiscoveredCompany

FAKE_RESULTS = [
    DiscoveredCompany(
        name="Acme Corp",
        website="https://acme.com",
        phone="+1 303-555-0100",
        address="123 Main St, Denver, CO",
        external_id="place-1",
    ),
    DiscoveredCompany(
        name="Other Co",
        website="https://other.com",
        phone=None,
        address="456 Elm St, Denver, CO",
        external_id="place-2",
    ),
]


def test_search_returns_candidates(client, auth_headers):
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=FAKE_RESULTS):
        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "marketing agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 2
    assert all(c["already_imported"] is False for c in candidates)


def test_search_marks_already_imported_company(client, auth_headers):
    client.post(
        "/api/v1/companies",
        json={"name": "Acme Corp", "website": "https://acme.com"},
        headers=auth_headers,
    )
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=FAKE_RESULTS):
        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "marketing agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    candidates = {c["external_id"]: c for c in response.json()["candidates"]}
    assert candidates["place-1"]["already_imported"] is True
    assert candidates["place-2"]["already_imported"] is False


def test_search_enforces_monthly_cap(client, auth_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "discovery_search_monthly_cap", 1)
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=[]):
        first = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limit_exceeded"


def test_search_cap_is_scoped_per_organization(client, auth_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "discovery_search_monthly_cap", 1)
    with patch("app.api.routes.discovery.GooglePlacesProvider.search", return_value=[]):
        client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=auth_headers,
        )

        other_register = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Other Org",
                "email": "other-discovery@example.com",
                "password": "password123",
            },
        )
        other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

        response = client.post(
            "/api/v1/discovery/search",
            json={"query": "agencies", "location": "Denver, CO"},
            headers=other_headers,
        )
    assert response.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_discovery_search.py -v`
Expected: FAIL — 404s (`/api/v1/discovery/search` doesn't exist yet).

- [ ] **Step 4: Add discovery schemas**

Create `apps/api/app/schemas/discovery.py`:

```python
from pydantic import BaseModel, Field


class DiscoverySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)


class DiscoveryCandidate(BaseModel):
    name: str
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    external_id: str
    already_imported: bool = False


class DiscoverySearchResponse(BaseModel):
    candidates: list[DiscoveryCandidate]
```

- [ ] **Step 5: Add the search route**

Create `apps/api/app/api/routes/discovery.py`:

```python
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.dedup import find_duplicate_company
from app.core.errors import RateLimitExceededError
from app.db import get_db
from app.models import ProviderSearchLog, User
from app.providers.google_places import GooglePlacesProvider
from app.schemas.discovery import DiscoveryCandidate, DiscoverySearchRequest, DiscoverySearchResponse

router = APIRouter(prefix="/discovery", tags=["discovery"])

PROVIDER_NAME = "google_places"


def _monthly_search_count(db: Session, organization_id: uuid.UUID) -> int:
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    return db.scalar(
        select(func.count())
        .select_from(ProviderSearchLog)
        .where(
            ProviderSearchLog.organization_id == organization_id,
            ProviderSearchLog.provider == PROVIDER_NAME,
            ProviderSearchLog.created_at >= month_start,
        )
    )


@router.post("/search", response_model=DiscoverySearchResponse)
def search(
    payload: DiscoverySearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if _monthly_search_count(db, current_user.organization_id) >= settings.discovery_search_monthly_cap:
        raise RateLimitExceededError()

    db.add(ProviderSearchLog(organization_id=current_user.organization_id, provider=PROVIDER_NAME))
    db.commit()

    results = GooglePlacesProvider().search(payload.query, payload.location)

    candidates = [
        DiscoveryCandidate(
            name=result.name,
            website=result.website,
            phone=result.phone,
            address=result.address,
            external_id=result.external_id,
            already_imported=find_duplicate_company(
                db, current_user.organization_id, result.external_id, result.website
            )
            is not None,
        )
        for result in results
    ]
    return DiscoverySearchResponse(candidates=candidates)
```

- [ ] **Step 6: Register the router**

In `apps/api/app/main.py`, change:

```python
from app.api.routes import auth, companies, health, leads
```

to:

```python
from app.api.routes import auth, companies, discovery, health, leads
```

and change:

```python
app.include_router(leads.router, prefix="/api/v1")
```

to:

```python
app.include_router(leads.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_discovery_search.py -v`
Expected: PASS (4 tests)

Then run the full suite to check nothing else broke: `uv run pytest -v`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/config.py .env.example apps/api/app/core/errors.py apps/api/app/schemas/discovery.py apps/api/app/api/routes/discovery.py apps/api/app/main.py apps/api/app/tests/test_discovery_search.py
git commit -m "feat(api): add discovery search endpoint with dedup marking and monthly cap"
```

---

### Task 7: Discovery import endpoint

**Files:**
- Modify: `apps/api/app/schemas/discovery.py`
- Modify: `apps/api/app/api/routes/discovery.py`
- Create: `apps/api/app/tests/test_discovery_import.py`

**Interfaces:**
- Consumes: `find_duplicate_company` (Task 2), `DiscoveryCandidate` (Task 6).
- Produces: `POST /api/v1/discovery/import`; `DiscoveryImportRequest`, `DiscoveryImportResponse` schemas.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/app/tests/test_discovery_import.py`:

```python
from app.models import Company, Lead


def _candidate(**overrides):
    base = {
        "name": "Acme Corp",
        "website": "https://acme.com",
        "phone": "+1 303-555-0100",
        "address": "123 Main St, Denver, CO",
        "external_id": "place-1",
        "already_imported": False,
    }
    base.update(overrides)
    return base


def test_import_creates_company_and_lead(client, auth_headers, db_session):
    payload = {"candidates": [_candidate()]}
    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 1, "skipped_duplicate": 0}

    company = db_session.query(Company).filter_by(external_id="place-1").one()
    assert company.name == "Acme Corp"
    assert company.source == "google_places"

    lead = db_session.query(Lead).filter_by(company_id=company.id).one()
    assert lead.status == "new"
    assert lead.contact_name is None
    assert lead.email is None


def test_import_skips_existing_duplicate(client, auth_headers):
    client.post(
        "/api/v1/companies", json={"name": "Acme Corp", "website": "https://acme.com"}, headers=auth_headers
    )
    payload = {"candidates": [_candidate(website="https://acme.com")]}
    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 0, "skipped_duplicate": 1}


def test_import_is_scoped_to_organization(client, auth_headers):
    other_register = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Org",
            "email": "other-import@example.com",
            "password": "password123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    payload = {"candidates": [_candidate()]}
    client.post("/api/v1/discovery/import", json=payload, headers=other_headers)

    response = client.post("/api/v1/discovery/import", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"created": 1, "skipped_duplicate": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/test_discovery_import.py -v`
Expected: FAIL — 404s (`/api/v1/discovery/import` doesn't exist yet).

- [ ] **Step 3: Add import schemas**

In `apps/api/app/schemas/discovery.py`, add at the end of the file:

```python
class DiscoveryImportRequest(BaseModel):
    candidates: list[DiscoveryCandidate]


class DiscoveryImportResponse(BaseModel):
    created: int
    skipped_duplicate: int
```

- [ ] **Step 4: Add the import route**

In `apps/api/app/api/routes/discovery.py`, change the import block from:

```python
from app.models import ProviderSearchLog, User
from app.providers.google_places import GooglePlacesProvider
from app.schemas.discovery import DiscoveryCandidate, DiscoverySearchRequest, DiscoverySearchResponse
```

to:

```python
from app.models import Company, Lead, ProviderSearchLog, User
from app.providers.google_places import GooglePlacesProvider
from app.schemas.discovery import (
    DiscoveryCandidate,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
)
```

Then add at the end of the file:

```python
@router.post("/import", response_model=DiscoveryImportResponse)
def import_candidates(
    payload: DiscoveryImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    created = 0
    skipped = 0
    for candidate in payload.candidates:
        duplicate = find_duplicate_company(
            db, current_user.organization_id, candidate.external_id, candidate.website
        )
        if duplicate is not None:
            skipped += 1
            continue

        company = Company(
            organization_id=current_user.organization_id,
            name=candidate.name,
            website=candidate.website,
            external_id=candidate.external_id,
            source=PROVIDER_NAME,
        )
        db.add(company)
        db.flush()

        lead = Lead(organization_id=current_user.organization_id, company_id=company.id, status="new")
        db.add(lead)
        created += 1

    db.commit()
    return DiscoveryImportResponse(created=created, skipped_duplicate=skipped)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest app/tests/test_discovery_import.py -v`
Expected: PASS (3 tests)

Then run the full suite: `uv run pytest -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/schemas/discovery.py apps/api/app/api/routes/discovery.py apps/api/app/tests/test_discovery_import.py
git commit -m "feat(api): add discovery import endpoint creating Company+Lead with dedup"
```

---

### Task 8: Frontend discover page

**Files:**
- Create: `apps/web/components/ui/checkbox.tsx` (generated by shadcn CLI)
- Modify: `apps/web/package.json` (+ `apps/web/pnpm-lock.yaml`, regenerated by CLI)
- Create: `apps/web/lib/discovery.ts`
- Create: `apps/web/app/(dashboard)/leads/discover/page.tsx`
- Modify: `apps/web/app/(dashboard)/layout.tsx`
- Modify: `apps/web/app/(dashboard)/leads/page.tsx`
- Create: `apps/web/e2e/discover.spec.ts`

**Interfaces:**
- Consumes: `POST /discovery/search`, `POST /discovery/import` (Tasks 6, 7); `apiFetch` from `apps/web/lib/api-client.ts`.

- [ ] **Step 1: Install the shadcn `checkbox` component**

From `apps/web`, run: `pnpm dlx shadcn@latest add checkbox`

This creates `apps/web/components/ui/checkbox.tsx` and updates `package.json`/`pnpm-lock.yaml`. Open the generated file and confirm the component's public props — it should expose `checked`, `onCheckedChange`, and `disabled` (the standard shadcn checkbox API); the wiring in Step 4 below assumes those names. If the generated component uses different prop names, adjust Step 4 accordingly to match.

- [ ] **Step 2: Add the discovery API client**

Create `apps/web/lib/discovery.ts`:

```typescript
import { apiFetch } from "./api-client";

export interface DiscoveryCandidate {
  name: string;
  website: string | null;
  phone: string | null;
  address: string | null;
  external_id: string;
  already_imported: boolean;
}

export interface DiscoverySearchResponse {
  candidates: DiscoveryCandidate[];
}

export interface DiscoveryImportResponse {
  created: number;
  skipped_duplicate: number;
}

export async function searchDiscovery(query: string, location: string): Promise<DiscoverySearchResponse> {
  return apiFetch<DiscoverySearchResponse>("/discovery/search", {
    method: "POST",
    body: JSON.stringify({ query, location }),
  });
}

export async function importDiscoveryCandidates(
  candidates: DiscoveryCandidate[],
): Promise<DiscoveryImportResponse> {
  return apiFetch<DiscoveryImportResponse>("/discovery/import", {
    method: "POST",
    body: JSON.stringify({ candidates }),
  });
}
```

- [ ] **Step 3: Add nav links to the dashboard header**

In `apps/web/app/(dashboard)/layout.tsx`, add the import:

```typescript
import Link from "next/link";
```

Change:

```tsx
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-4">
        <span className="font-semibold text-neutral-900">B2B Campaign</span>
        {user && (
```

to:

```tsx
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-4">
        <div className="flex items-center gap-6">
          <span className="font-semibold text-neutral-900">B2B Campaign</span>
          <nav className="flex items-center gap-4 text-sm text-neutral-600">
            <Link href="/leads" className="hover:text-neutral-900">
              Leads
            </Link>
            <Link href="/leads/discover" className="hover:text-neutral-900">
              Discover
            </Link>
          </nav>
        </div>
        {user && (
```

- [ ] **Step 4: Build the discover page**

Create `apps/web/app/(dashboard)/leads/discover/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { type DiscoveryCandidate, importDiscoveryCandidates, searchDiscovery } from "@/lib/discovery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DiscoverPage() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [candidates, setCandidates] = useState<DiscoveryCandidate[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [summary, setSummary] = useState<{ created: number; skipped_duplicate: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSummary(null);
    setLoading(true);
    try {
      const response = await searchDiscovery(query, location);
      setCandidates(response.candidates);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function toggleSelected(externalId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(externalId)) {
        next.delete(externalId);
      } else {
        next.add(externalId);
      }
      return next;
    });
  }

  async function handleImport() {
    if (!candidates) return;
    const toImport = candidates.filter((c) => selected.has(c.external_id));
    if (toImport.length === 0) return;
    setError(null);
    setImporting(true);
    try {
      const response = await importDiscoveryCandidates(toImport);
      setSummary(response);
      setCandidates((prev) =>
        prev
          ? prev.map((c) => (selected.has(c.external_id) ? { ...c, already_imported: true } : c))
          : prev,
      );
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h1 className="text-lg font-medium text-neutral-900">Discover leads</h1>
        <p className="mt-1 text-sm text-neutral-500">Search Google Places for companies to import as leads.</p>
        <form onSubmit={handleSearch} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="query">What</Label>
            <Input
              id="query"
              placeholder="marketing agencies"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="location">Where</Label>
            <Input
              id="location"
              placeholder="Denver, CO"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </Button>
        </form>
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      </Card>

      {summary && (
        <div className="rounded-lg border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700">
          Imported {summary.created} {summary.created === 1 ? "lead" : "leads"}
          {summary.skipped_duplicate > 0 &&
            ` (${summary.skipped_duplicate} skipped as ${
              summary.skipped_duplicate === 1 ? "duplicate" : "duplicates"
            })`}
          .
        </div>
      )}

      {candidates && (
        <div className="rounded-lg border border-neutral-200 bg-white">
          {candidates.length === 0 ? (
            <p className="p-6 text-sm text-neutral-500">No results.</p>
          ) : (
            <>
              <ul className="divide-y divide-neutral-200">
                {candidates.map((candidate) => (
                  <li key={candidate.external_id} className="flex items-center gap-3 px-4 py-3">
                    <Checkbox
                      checked={selected.has(candidate.external_id)}
                      disabled={candidate.already_imported}
                      onCheckedChange={() => toggleSelected(candidate.external_id)}
                    />
                    <div className="flex-1 text-sm">
                      <div className="font-medium text-neutral-900">{candidate.name}</div>
                      <div className="text-neutral-500">
                        {[candidate.address, candidate.phone, candidate.website].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    {candidate.already_imported && <Badge variant="outline">Already imported</Badge>}
                  </li>
                ))}
              </ul>
              <div className="border-t border-neutral-200 px-4 py-3">
                <Button onClick={handleImport} disabled={selected.size === 0 || importing}>
                  {importing ? "Importing…" : `Import selected (${selected.size})`}
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Point the empty leads state at the discover page**

In `apps/web/app/(dashboard)/leads/page.tsx`, add the import:

```typescript
import Link from "next/link";
```

Change:

```tsx
    return (
      <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-12 text-center">
        <h2 className="text-lg font-medium text-neutral-900">No leads yet</h2>
        <p className="mt-2 text-sm text-neutral-500">
          Lead discovery and import are coming in the next release.
        </p>
      </div>
    );
```

to:

```tsx
    return (
      <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-12 text-center">
        <h2 className="text-lg font-medium text-neutral-900">No leads yet</h2>
        <p className="mt-2 text-sm text-neutral-500">Search for companies to import as leads.</p>
        <Link
          href="/leads/discover"
          className="mt-4 inline-block text-sm font-medium text-neutral-900 underline underline-offset-4"
        >
          Discover leads
        </Link>
      </div>
    );
```

- [ ] **Step 6: Write the e2e test**

Create `apps/web/e2e/discover.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";

test("search, select, and import a discovered lead", async ({ page }) => {
  const email = `discover-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Organization name").fill("Discover Test Org");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /register/i }).click();
  await expect(page).toHaveURL(/\/leads/);

  await page.route("**/api/v1/discovery/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        candidates: [
          {
            name: "Acme Corp",
            website: "https://acme.com",
            phone: "+1 303-555-0100",
            address: "123 Main St, Denver, CO",
            external_id: "place-1",
            already_imported: false,
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/discovery/import", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ created: 1, skipped_duplicate: 0 }),
    });
  });

  await page.getByRole("link", { name: "Discover" }).click();
  await expect(page).toHaveURL(/\/leads\/discover/);

  await page.getByLabel("What").fill("marketing agencies");
  await page.getByLabel("Where").fill("Denver, CO");
  await page.getByRole("button", { name: /^search$/i }).click();

  await expect(page.getByText("Acme Corp")).toBeVisible();

  await page.getByRole("checkbox").click();
  await page.getByRole("button", { name: /import selected/i }).click();

  await expect(page.getByText(/imported 1 lead/i)).toBeVisible();
});
```

- [ ] **Step 7: Run the e2e test**

From `apps/web`, with the dev stack running (`docker compose up` from the repo root, or `pnpm dev` + the API running separately per the README): `pnpm test:e2e discover.spec.ts`
Expected: PASS (1 test)

If no running stack is available in your environment, at minimum run `pnpm lint` and `pnpm build` from `apps/web` to confirm the new page and component compile and typecheck cleanly.

- [ ] **Step 8: Commit**

```bash
git add apps/web/components/ui/checkbox.tsx apps/web/package.json apps/web/pnpm-lock.yaml apps/web/lib/discovery.ts "apps/web/app/(dashboard)/leads/discover/page.tsx" "apps/web/app/(dashboard)/layout.tsx" "apps/web/app/(dashboard)/leads/page.tsx" apps/web/e2e/discover.spec.ts
git commit -m "feat(web): add lead discovery search/import page"
```

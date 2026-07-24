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
from app.models import Company, Lead, ProviderSearchLog, User
from app.providers.google_places import GooglePlacesProvider
from app.schemas.discovery import (
    DiscoveryCandidate,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
)

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

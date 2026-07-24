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

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.db import get_db
from app.models import Company, Lead, User
from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])


def _validate_company(db: Session, current_user: User, company_id: uuid.UUID | None) -> None:
    if company_id is None:
        return
    company = db.get(Company, company_id)
    if company is None or company.organization_id != current_user.organization_id:
        raise NotFoundError("Company not found")


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


@router.get("", response_model=list[LeadResponse])
def list_leads(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.scalars(select(Lead).where(Lead.organization_id == current_user.organization_id)).all()


def _get_lead_or_404(db: Session, current_user: User, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.organization_id != current_user.organization_id:
        raise NotFoundError("Lead not found")
    return lead


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_lead_or_404(db, current_user, lead_id)


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


@router.delete("/{lead_id}", status_code=204)
def delete_lead(
    lead_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    lead = _get_lead_or_404(db, current_user, lead_id)
    db.delete(lead)
    db.commit()

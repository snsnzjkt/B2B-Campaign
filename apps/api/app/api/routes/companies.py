import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.db import get_db
from app.models import Company, User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=201)
def create_company(
    payload: CompanyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    company = Company(organization_id=current_user.organization_id, **payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("", response_model=list[CompanyResponse])
def list_companies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.scalars(select(Company).where(Company.organization_id == current_user.organization_id)).all()


def _get_company_or_404(db: Session, current_user: User, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None or company.organization_id != current_user.organization_id:
        raise NotFoundError("Company not found")
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return _get_company_or_404(db, current_user, company_id)


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company_or_404(db, current_user, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    company = _get_company_or_404(db, current_user, company_id)
    db.delete(company)
    db.commit()

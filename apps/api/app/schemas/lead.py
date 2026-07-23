import uuid
from datetime import datetime

from pydantic import BaseModel


class LeadCreate(BaseModel):
    company_id: uuid.UUID | None = None
    contact_name: str | None = None
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None


class LeadUpdate(BaseModel):
    company_id: uuid.UUID | None = None
    contact_name: str | None = None
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    score: int | None = None


class LeadResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID | None
    contact_name: str | None
    job_title: str | None
    email: str | None
    phone: str | None
    email_verified: bool
    score: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

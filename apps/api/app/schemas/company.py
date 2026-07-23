import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str | None = None
    industry: str | None = None
    size_range: str | None = None
    location: str | None = None
    description: str | None = None
    social_links: dict = Field(default_factory=dict)


class CompanyUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    industry: str | None = None
    size_range: str | None = None
    location: str | None = None
    description: str | None = None
    social_links: dict | None = None


class CompanyResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    website: str | None
    industry: str | None
    size_range: str | None
    location: str | None
    description: str | None
    social_links: dict
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}

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


class DiscoveryImportRequest(BaseModel):
    candidates: list[DiscoveryCandidate]


class DiscoveryImportResponse(BaseModel):
    created: int
    skipped_duplicate: int

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # NOTE: the `leads` relationship (back_populates="company") is intentionally deferred to
    # Task 9, added alongside the `Lead` model. Registering a `relationship()` with a string
    # forward-reference to a class that isn't mapped yet ("Lead") makes SQLAlchemy's global
    # mapper configuration fail on the *first* ORM query anywhere in the app (not just for
    # Company) — confirmed empirically: it broke test_auth, test_google_auth, and test_models
    # in addition to test_companies. The Task 8 interface contract for Company does not list
    # `leads`, so omitting it here is interface-compatible; Task 9 should add both this
    # relationship and Lead.company together.

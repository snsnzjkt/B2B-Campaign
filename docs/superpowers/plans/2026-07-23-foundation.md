# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the monorepo, Docker dev environment, auth (JWT + Google OAuth), and the core Organization/User/Company/Lead data model that every later B2B outreach sub-project builds on.

**Architecture:** A two-app monorepo — FastAPI + SQLAlchemy (sync) + Alembic backend in `apps/api`, Next.js App Router + TypeScript + Tailwind + shadcn/ui frontend in `apps/web` — sharing nothing but the HTTP API contract. Postgres and Redis run via Docker Compose (Redis is provisioned now but unused until the Celery-based sub-project 4). Every domain table is scoped by `organization_id`; all API routes except `/health` and `/auth/*` require a valid JWT.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (sync, psycopg2), Alembic, pydantic v2, `uv`; Next.js 15, TypeScript, Tailwind, shadcn/ui, pnpm; Postgres 16, Redis 7; Docker Compose; GitHub Actions.

## Global Constraints

- Every domain table (`companies`, `leads`, and all future tables) has an `organization_id` foreign key and every query filters on it — no cross-tenant data leakage.
- API error responses always use the shape `{code, message, details}` (from the approved spec's Error Handling section).
- Backend tests run against in-memory SQLite (fast, no external services required); Postgres via Docker Compose is used for local dev and the real migration path — do not couple tests to a running Postgres container.
- Lead sourcing/crawling/sending features are explicitly out of scope for this plan (deferred to sub-projects 2–4) — do not add them here even incidentally.
- Default email/LLM adapters (SendGrid, Ollama/Groq) are not part of this plan; only the auth/data/CRUD foundation is built now.
- Secrets (SECRET_KEY, GOOGLE_CLIENT_ID, etc.) come from environment variables via `.env`, never hardcoded.

---

### Task 1: Repo scaffold and Docker Compose base services

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `README.md`

**Interfaces:**
- Produces: root `docker-compose.yml` with `db` (Postgres 16, port 5432, db name `b2b_campaign`, user/password `postgres`/`postgres`) and `redis` (Redis 7, port 6379) services — later tasks append `api` and `web` services to this same file.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/

# Node
node_modules/
.next/
out/

# Env
.env
!.env.example

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Create `.env.example`**

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/b2b_campaign
SECRET_KEY=change-me-to-a-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
GOOGLE_CLIENT_ID=
CORS_ORIGINS=["http://localhost:3000"]
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: b2b_campaign
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  db_data:
```

- [ ] **Step 4: Create a stub `README.md`**

```markdown
# B2B Lead Discovery & Outreach Platform

Foundation setup instructions land here as the project is built. See
`docs/superpowers/specs/2026-07-23-foundation-design.md` for the design.
```

- [ ] **Step 5: Verify Docker Compose config is valid**

Run: `docker compose config --quiet`
Expected: no output, exit code 0.

- [ ] **Step 6: Start the base services and verify Postgres is healthy**

Run: `docker compose up -d db redis && docker compose ps`
Expected: both `db` and `redis` show state `running` (db eventually `healthy`).

- [ ] **Step 7: Commit**

```bash
git add .gitignore .env.example docker-compose.yml README.md
git commit -m "chore: scaffold repo with Docker Compose base services"
```

---

### Task 2: Backend project init — FastAPI skeleton, config, DB session, health check

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/config.py`
- Create: `apps/api/app/db.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/api/__init__.py`
- Create: `apps/api/app/api/routes/__init__.py`
- Create: `apps/api/app/api/routes/health.py`
- Create: `apps/api/app/tests/__init__.py`
- Create: `apps/api/app/tests/conftest.py`
- Create: `apps/api/app/tests/test_health.py`
- Create: `apps/api/Dockerfile`
- Modify: `docker-compose.yml` (add `api` service)

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `.database_url`, `.secret_key`, `.access_token_expire_minutes`, `.refresh_token_expire_days`, `.google_client_id`, `.cors_origins`); `app.db.Base` (SQLAlchemy declarative base), `app.db.get_db()` (FastAPI dependency yielding a `Session`); `app.main.app` (the FastAPI instance); test fixtures `client` and `db_session` in `app/tests/conftest.py`.

- [ ] **Step 1: Create `apps/api/pyproject.toml`**

```toml
[project]
name = "b2b-campaign-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "pydantic-settings>=2.6",
    "passlib[bcrypt]>=1.7",
    "python-jose[cryptography]>=3.3",
    "google-auth>=2.35",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "httpx>=0.27",
    "ruff>=0.7",
]

[tool.pytest.ini_options]
pythonpath = ["."]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Install dependencies**

Run: `cd apps/api && uv sync`
Expected: `.venv` created, "Resolved N packages" / "Installed N packages" printed, exit code 0.

- [ ] **Step 3: Create `apps/api/app/__init__.py`** (empty file)

- [ ] **Step 4: Create `apps/api/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/b2b_campaign"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    google_client_id: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
```

- [ ] **Step 5: Create `apps/api/app/db.py`**

```python
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Create `apps/api/app/api/__init__.py`** and **`apps/api/app/api/routes/__init__.py`** (both empty)

- [ ] **Step 7: Create `apps/api/app/api/routes/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 8: Create `apps/api/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.config import settings

app = FastAPI(title="B2B Campaign API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
```

- [ ] **Step 9: Create `apps/api/app/tests/__init__.py`** (empty file)

- [ ] **Step 10: Create `apps/api/app/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Test Org", "email": "test@example.com", "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

Note: `auth_headers` references the `/api/v1/auth/register` endpoint built in Task 6 — it is added here so later test files can rely on it without editing conftest again, but it will only pass once Task 6 is complete. That's expected; this task's own test (`test_health.py`) does not use it.

- [ ] **Step 11: Create `apps/api/app/tests/test_health.py`**

```python
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `cd apps/api && uv run pytest app/tests/test_health.py -v`
Expected: `1 passed`.

- [ ] **Step 13: Create `apps/api/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv sync --no-dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 14: Add the `api` service to root `docker-compose.yml`**

Add this service under `services:`, after `redis`, and keep the existing `volumes:` block at the end:

```yaml
  api:
    build: ./apps/api
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://postgres:postgres@db:5432/b2b_campaign
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./apps/api:/app
```

- [ ] **Step 15: Verify Docker Compose config is still valid**

Run: `docker compose config --quiet`
Expected: no output, exit code 0.

- [ ] **Step 16: Commit**

```bash
git add apps/api docker-compose.yml
git commit -m "feat(api): scaffold FastAPI app with config, DB session, and health check"
```

---

### Task 3: Alembic setup, Organization and User models, initial migration

**Files:**
- Create: `apps/api/app/models/__init__.py`
- Create: `apps/api/app/models/organization.py`
- Create: `apps/api/app/models/user.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/script.py.mako`
- Create: `apps/api/alembic/versions/` (via autogenerate in Step 6)
- Test: `apps/api/app/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.Organization(id, name, created_at, users)`, `app.models.User(id, organization_id, email, hashed_password, oauth_provider, oauth_id, role, created_at, organization)`. Both importable from `app.models`.

- [ ] **Step 1: Create `apps/api/app/models/organization.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization")
```

- [ ] **Step 2: Create `apps/api/app/models/user.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="users")
```

- [ ] **Step 3: Create `apps/api/app/models/__init__.py`**

```python
from app.models.organization import Organization
from app.models.user import User

__all__ = ["Organization", "User"]
```

- [ ] **Step 4: Create `apps/api/app/tests/test_models.py`**

```python
from app.models import Organization, User


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
```

Note: this test relies on `app.models` being imported so the tables are registered on `Base.metadata` before `conftest.py`'s `Base.metadata.create_all(engine)` runs. Update `apps/api/app/tests/conftest.py`'s imports to include `import app.models  # noqa: F401` right after `from app.db import Base, get_db`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd apps/api && uv run pytest app/tests/test_models.py -v`
Expected: `1 passed`.

- [ ] **Step 6: Initialize Alembic**

Run: `cd apps/api && uv run alembic init alembic`
Expected: creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 7: Replace `apps/api/alembic/env.py` contents**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401
from app.config import settings
from app.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Ensure Postgres is running and generate the initial migration**

Run: `docker compose up -d db && cd apps/api && uv run alembic revision --autogenerate -m "create organizations and users tables"`
Expected: a new file under `apps/api/alembic/versions/` containing `op.create_table("organizations", ...)` and `op.create_table("users", ...)`.

- [ ] **Step 9: Apply the migration**

Run: `cd apps/api && uv run alembic upgrade head`
Expected: output ends with `Running upgrade  -> <revision>, create organizations and users tables`.

- [ ] **Step 10: Commit**

```bash
git add apps/api/app/models apps/api/app/tests apps/api/alembic apps/api/alembic.ini
git commit -m "feat(api): add Organization and User models with initial migration"
```

---

### Task 4: Security utilities — password hashing and JWT

**Files:**
- Create: `apps/api/app/core/__init__.py`
- Create: `apps/api/app/core/security.py`
- Test: `apps/api/app/tests/test_security.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, hashed: str) -> bool`, `create_token(subject: str, expires_delta: timedelta, token_type: str) -> str`, `create_access_token(user_id: str) -> str`, `create_refresh_token(user_id: str) -> str`, `decode_token(token: str) -> dict`.

- [ ] **Step 1: Write the failing tests — create `apps/api/app/tests/test_security.py`**

```python
from datetime import timedelta

import pytest
from jose import ExpiredSignatureError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_verifies_correct_password():
    hashed = hash_password("s3cret-pw")
    assert verify_password("s3cret-pw", hashed) is True


def test_hash_password_rejects_wrong_password():
    hashed = hash_password("s3cret-pw")
    assert verify_password("wrong-pw", hashed) is False


def test_access_token_round_trip():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_round_trip():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_expired_token_raises():
    token = create_token("user-123", timedelta(seconds=-1), "access")
    with pytest.raises(ExpiredSignatureError):
        decode_token(token)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest app/tests/test_security.py -v`
Expected: `ModuleNotFoundError: No module named 'app.core'`.

- [ ] **Step 3: Create `apps/api/app/core/__init__.py`** (empty file)

- [ ] **Step 4: Create `apps/api/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(user_id: str) -> str:
    return create_token(user_id, timedelta(minutes=settings.access_token_expire_minutes), "access")


def create_refresh_token(user_id: str) -> str:
    return create_token(user_id, timedelta(days=settings.refresh_token_expire_days), "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest app/tests/test_security.py -v`
Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core apps/api/app/tests/test_security.py
git commit -m "feat(api): add password hashing and JWT utilities"
```

---

### Task 5: Consistent error handling

**Files:**
- Create: `apps/api/app/core/errors.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/app/tests/test_errors.py`

**Interfaces:**
- Produces: `AppError(code, message, status_code=400, details=None)`, `NotFoundError(message="Resource not found", details=None)`, `InvalidCredentialsError()`, `TokenExpiredError()`, `InvalidTokenError()`, `ConflictError(message, details=None)`. All raised as exceptions and turned into `{code, message, details}` JSON by a FastAPI exception handler registered in `app.main`.

- [ ] **Step 1: Write the failing test — create `apps/api/app/tests/test_errors.py`**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, NotFoundError


def test_app_error_returns_consistent_shape():
    app = FastAPI()

    from app.main import app_error_handler

    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/boom")
    def boom():
        raise NotFoundError("Widget not found", details={"widget_id": "42"})

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "message": "Widget not found",
        "details": {"widget_id": "42"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest app/tests/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'app.core.errors'` (or `ImportError: cannot import name 'app_error_handler'`).

- [ ] **Step 3: Create `apps/api/app/core/errors.py`**

```python
class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(code="not_found", message=message, status_code=404, details=details)


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__(code="invalid_credentials", message="Invalid email or password", status_code=401)


class TokenExpiredError(AppError):
    def __init__(self):
        super().__init__(code="token_expired", message="Token has expired", status_code=401)


class InvalidTokenError(AppError):
    def __init__(self):
        super().__init__(code="invalid_token", message="Token is invalid", status_code=401)


class ConflictError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(code="conflict", message=message, status_code=409, details=details)
```

- [ ] **Step 4: Register the handler in `apps/api/app/main.py`**

Replace the file with:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.config import settings
from app.core.errors import AppError

app = FastAPI(title="B2B Campaign API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


app.add_exception_handler(AppError, app_error_handler)

app.include_router(health.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/api && uv run pytest app/tests/test_errors.py -v`
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core/errors.py apps/api/app/main.py apps/api/app/tests/test_errors.py
git commit -m "feat(api): add consistent AppError JSON error shape"
```

---

### Task 6: Auth endpoints — register, login, refresh, me

**Files:**
- Create: `apps/api/app/schemas/__init__.py`
- Create: `apps/api/app/schemas/auth.py`
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/api/routes/auth.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/app/tests/test_auth.py`

**Interfaces:**
- Consumes: `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token` from Task 4; `AppError` subclasses from Task 5; `Organization`, `User` from Task 3.
- Produces: `app.api.deps.get_current_user` (FastAPI dependency returning a `User`, raising `InvalidTokenError`/`TokenExpiredError`); router mounted at `/api/v1/auth` with `POST /register`, `POST /login`, `POST /refresh`, `GET /me`. Later tasks (companies, leads) depend on `get_current_user`.

- [ ] **Step 1: Create `apps/api/app/schemas/__init__.py`** (empty file)

- [ ] **Step 2: Create `apps/api/app/schemas/auth.py`**

```python
import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create `apps/api/app/api/deps.py`**

```python
import uuid

from fastapi import Depends, Header
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.orm import Session

from app.core.errors import InvalidTokenError, TokenExpiredError
from app.core.security import decode_token
from app.db import get_db
from app.models import User


def get_user_by_sub(db: Session, sub: str) -> User | None:
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        return None
    return db.get(User, user_id)


def get_current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise InvalidTokenError()
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise InvalidTokenError()
    if payload.get("type") != "access":
        raise InvalidTokenError()
    user = get_user_by_sub(db, payload.get("sub", ""))
    if user is None:
        raise InvalidTokenError()
    return user
```

- [ ] **Step 4: Create `apps/api/app/api/routes/auth.py`**

```python
from fastapi import APIRouter, Depends
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_user_by_sub
from app.core.errors import ConflictError, InvalidCredentialsError, InvalidTokenError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models import Organization, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise ConflictError("An account with this email already exists")

    org = Organization(name=payload.organization_name)
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or user.hashed_password is None or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
    except JWTError:
        raise InvalidTokenError()
    if data.get("type") != "refresh":
        raise InvalidTokenError()
    user = get_user_by_sub(db, data.get("sub", ""))
    if user is None:
        raise InvalidTokenError()
    return _tokens_for(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 5: Mount the router in `apps/api/app/main.py`**

Add `from app.api.routes import auth, health` (replacing the `health`-only import) and, after `app.include_router(health.router)`, add:

```python
app.include_router(auth.router, prefix="/api/v1")
```

- [ ] **Step 6: Create `apps/api/app/tests/test_auth.py`**

```python
def test_register_creates_org_and_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "founder@acme.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_register_rejects_duplicate_email(client):
    payload = {"organization_name": "Acme Inc", "email": "dup@acme.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_login_succeeds_with_correct_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "login@acme.com", "password": "password123"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "login@acme.com", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "wrong@acme.com", "password": "password123"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "wrong@acme.com", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "me@acme.com", "password": "password123"},
    )
    token = register.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@acme.com"


def test_refresh_issues_new_access_token(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "refresh@acme.com", "password": "password123"},
    )
    refresh_token = register.json()["refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest app/tests/test_auth.py -v`
Expected: `7 passed`.

- [ ] **Step 8: Run the full test suite to confirm the `auth_headers` fixture in `conftest.py` now works**

Run: `cd apps/api && uv run pytest -v`
Expected: all tests pass, including any that use `auth_headers`.

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/schemas apps/api/app/api apps/api/app/main.py apps/api/app/tests/test_auth.py
git commit -m "feat(api): add register/login/refresh/me auth endpoints"
```

---

### Task 7: Google OAuth endpoint

**Files:**
- Modify: `apps/api/app/schemas/auth.py`
- Modify: `apps/api/app/api/routes/auth.py`
- Test: `apps/api/app/tests/test_google_auth.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/google` accepting `{id_token}`, verifying it against `settings.google_client_id` via `google.oauth2.id_token.verify_oauth2_token`, creating a new `User`+`Organization` on first login (org name defaults to the email's local part) or linking an existing user by email, and returning `TokenResponse`.

- [ ] **Step 1: Add `GoogleAuthRequest` to `apps/api/app/schemas/auth.py`** (append below `RefreshRequest`)

```python
class GoogleAuthRequest(BaseModel):
    id_token: str
```

(If already present from Task 6's file, skip — Task 6's schema file already includes it.)

- [ ] **Step 2: Write the failing test — create `apps/api/app/tests/test_google_auth.py`**

```python
from unittest.mock import patch


def test_google_auth_creates_new_user(client):
    fake_info = {"email": "newuser@gmail.com", "sub": "google-sub-123"}
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", return_value=fake_info):
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


def test_google_auth_links_existing_user_by_email(client):
    client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme Inc", "email": "existing@acme.com", "password": "password123"},
    )
    fake_info = {"email": "existing@acme.com", "sub": "google-sub-456"}
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", return_value=fake_info):
        response = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200


def test_google_auth_rejects_invalid_token(client):
    with patch("app.api.routes.auth.id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
        response = client.post("/api/v1/auth/google", json={"id_token": "bad"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest app/tests/test_google_auth.py -v`
Expected: `404 != 200` (route does not exist yet) or `AttributeError` on the patch target.

- [ ] **Step 4: Add the Google auth route to `apps/api/app/api/routes/auth.py`**

Add these imports at the top:

```python
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings
from app.schemas.auth import GoogleAuthRequest
```

Add this route at the end of the file:

```python
@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        info = id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise InvalidTokenError()

    email = info["email"]
    google_sub = info["sub"]

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        org = Organization(name=email.split("@")[0])
        db.add(org)
        db.flush()
        user = User(
            organization_id=org.id,
            email=email,
            oauth_provider="google",
            oauth_id=google_sub,
            role="owner",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.oauth_provider is None:
        user.oauth_provider = "google"
        user.oauth_id = google_sub
        db.commit()

    return _tokens_for(user)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest app/tests/test_google_auth.py -v`
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/routes/auth.py apps/api/app/schemas/auth.py apps/api/app/tests/test_google_auth.py
git commit -m "feat(api): add Google OAuth login endpoint"
```

---

### Task 8: Company model, schema, and CRUD routes

**Files:**
- Create: `apps/api/app/models/company.py`
- Modify: `apps/api/app/models/__init__.py`
- Create: `apps/api/app/schemas/company.py`
- Create: `apps/api/app/api/routes/companies.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/app/tests/test_companies.py`

**Interfaces:**
- Produces: `app.models.Company(id, organization_id, name, website, industry, size_range, location, description, social_links, source, created_at)`; router at `/api/v1/companies` with `POST`, `GET` (list), `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, all scoped to `current_user.organization_id`.

- [ ] **Step 1: Create `apps/api/app/models/company.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    leads: Mapped[list["Lead"]] = relationship(back_populates="company")
```

- [ ] **Step 2: Update `apps/api/app/models/__init__.py`**

```python
from app.models.company import Company
from app.models.organization import Organization
from app.models.user import User

__all__ = ["Company", "Organization", "User"]
```

(Note: `Lead` will be added here in Task 9 — the `Company.leads` relationship string reference `"Lead"` will resolve once that model is registered on the same `Base`.)

- [ ] **Step 3: Create `apps/api/app/schemas/company.py`**

```python
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
```

- [ ] **Step 4: Create `apps/api/app/api/routes/companies.py`**

```python
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
```

- [ ] **Step 5: Mount the router in `apps/api/app/main.py`**

Change the import to `from app.api.routes import auth, companies, health` and add:

```python
app.include_router(companies.router, prefix="/api/v1")
```

- [ ] **Step 6: Create `apps/api/app/tests/test_companies.py`**

```python
def test_create_and_list_company(client, auth_headers):
    response = client.post(
        "/api/v1/companies", json={"name": "Acme Corp", "website": "https://acme.com"}, headers=auth_headers
    )
    assert response.status_code == 201
    company_id = response.json()["id"]

    listing = client.get("/api/v1/companies", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == company_id


def test_get_company_not_found(client, auth_headers):
    response = client.get(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_update_company(client, auth_headers):
    create = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/companies/{company_id}", json={"industry": "Software"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["industry"] == "Software"


def test_delete_company(client, auth_headers):
    create = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = create.json()["id"]
    response = client.delete(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert response.status_code == 204
    get_response = client.get(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_companies_are_scoped_to_organization(client, auth_headers):
    client.post("/api/v1/companies", json={"name": "Org A Co"}, headers=auth_headers)

    other_register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Other Org", "email": "other@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    listing = client.get("/api/v1/companies", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest app/tests/test_companies.py -v`
Expected: `5 passed`.

- [ ] **Step 8: Generate and apply the migration**

Run: `docker compose up -d db && cd apps/api && uv run alembic revision --autogenerate -m "create companies table" && uv run alembic upgrade head`
Expected: new revision file created; output ends with `Running upgrade ... create companies table`.

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/models apps/api/app/schemas/company.py apps/api/app/api/routes/companies.py apps/api/app/main.py apps/api/app/tests/test_companies.py apps/api/alembic
git commit -m "feat(api): add Company model with CRUD endpoints"
```

---

### Task 9: Lead model, schema, and CRUD routes

**Files:**
- Create: `apps/api/app/models/lead.py`
- Modify: `apps/api/app/models/__init__.py`
- Create: `apps/api/app/schemas/lead.py`
- Create: `apps/api/app/api/routes/leads.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/app/tests/test_leads.py`

**Interfaces:**
- Produces: `app.models.Lead(id, organization_id, company_id, contact_name, job_title, email, phone, email_verified, score, status, created_at)`; router at `/api/v1/leads` with `POST`, `GET` (list), `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, scoped to `current_user.organization_id`; `company_id`, if provided, must belong to the same organization or the request 404s.

- [ ] **Step 1: Create `apps/api/app/models/lead.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company | None"] = relationship(back_populates="leads")
```

- [ ] **Step 2: Update `apps/api/app/models/__init__.py`**

```python
from app.models.company import Company
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.user import User

__all__ = ["Company", "Lead", "Organization", "User"]
```

- [ ] **Step 3: Create `apps/api/app/schemas/lead.py`**

```python
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
```

- [ ] **Step 4: Create `apps/api/app/api/routes/leads.py`**

```python
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
```

- [ ] **Step 5: Mount the router in `apps/api/app/main.py`**

Change the import to `from app.api.routes import auth, companies, health, leads` and add:

```python
app.include_router(leads.router, prefix="/api/v1")
```

- [ ] **Step 6: Create `apps/api/app/tests/test_leads.py`**

```python
def test_create_lead_without_company(client, auth_headers):
    response = client.post(
        "/api/v1/leads", json={"contact_name": "Jane Doe", "email": "jane@example.com"}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "new"


def test_create_lead_with_valid_company(client, auth_headers):
    company = client.post("/api/v1/companies", json={"name": "Acme Corp"}, headers=auth_headers)
    company_id = company.json()["id"]
    response = client.post(
        "/api/v1/leads",
        json={"contact_name": "Jane Doe", "company_id": company_id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["company_id"] == company_id


def test_create_lead_with_unknown_company_404s(client, auth_headers):
    response = client.post(
        "/api/v1/leads",
        json={"contact_name": "Jane Doe", "company_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_list_leads_empty_by_default(client, auth_headers):
    response = client.get("/api/v1/leads", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_update_lead_status_and_score(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    response = client.patch(
        f"/api/v1/leads/{lead_id}", json={"status": "qualified", "score": 80}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "qualified"
    assert response.json()["score"] == 80


def test_delete_lead(client, auth_headers):
    create = client.post("/api/v1/leads", json={"contact_name": "Jane Doe"}, headers=auth_headers)
    lead_id = create.json()["id"]
    response = client.delete(f"/api/v1/leads/{lead_id}", headers=auth_headers)
    assert response.status_code == 204
    get_response = client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_leads_are_scoped_to_organization(client, auth_headers):
    client.post("/api/v1/leads", json={"contact_name": "Org A Lead"}, headers=auth_headers)

    other_register = client.post(
        "/api/v1/auth/register",
        json={"organization_name": "Other Org", "email": "other-leads@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    listing = client.get("/api/v1/leads", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest app/tests/test_leads.py -v`
Expected: `7 passed`.

- [ ] **Step 8: Run the full backend test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: all tests pass (health, models, security, errors, auth, google auth, companies, leads).

- [ ] **Step 9: Generate and apply the migration**

Run: `docker compose up -d db && cd apps/api && uv run alembic revision --autogenerate -m "create leads table" && uv run alembic upgrade head`
Expected: new revision file created; output ends with `Running upgrade ... create leads table`.

- [ ] **Step 10: Commit**

```bash
git add apps/api/app/models apps/api/app/schemas/lead.py apps/api/app/api/routes/leads.py apps/api/app/main.py apps/api/app/tests/test_leads.py apps/api/alembic
git commit -m "feat(api): add Lead model with CRUD endpoints"
```

---

### Task 10: Backend CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a GitHub Actions workflow with a job named `api` running `ruff check` and `pytest` on push/PR. A `web` job is appended to this same file in Task 14.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  api:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -v
```

- [ ] **Step 2: Verify the workflow YAML is well-formed**

Run: `docker run --rm -v "$(pwd)/.github/workflows/ci.yml:/ci.yml" mikefarah/yq eval /ci.yml` (or, if that image isn't available, `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` from the repo root)
Expected: no errors, the parsed structure prints or is silently valid.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add backend lint and test workflow"
```

---

### Task 11: Frontend scaffold — Next.js, Tailwind, shadcn/ui

**Files:**
- Create: `apps/web/` (via `create-next-app`)
- Modify: `apps/web/` (via `shadcn` CLI: `components.json`, `components/ui/button.tsx`, `components/ui/input.tsx`, `components/ui/label.tsx`, `components/ui/card.tsx`, `lib/utils.ts`)
- Create: `apps/web/Dockerfile`
- Modify: `docker-compose.yml` (add `web` service)

**Interfaces:**
- Produces: a running Next.js app at `apps/web` with Tailwind configured and shadcn/ui primitives available at `@/components/ui/{button,input,label,card}` and the `cn()` helper at `@/lib/utils`.

- [ ] **Step 1: Scaffold the Next.js app**

Run (from repo root): `pnpm create next-app@latest apps/web --typescript --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-pnpm --yes`
Expected: `apps/web` created with a working Next.js app; command exits 0.

- [ ] **Step 2: Initialize shadcn/ui**

Run: `cd apps/web && pnpm dlx shadcn@latest init -d`
Expected: `components.json` created, `lib/utils.ts` created, `app/globals.css` updated with theme tokens.

- [ ] **Step 3: Add the UI primitives this plan's pages need**

Run: `cd apps/web && pnpm dlx shadcn@latest add button input label card -y`
Expected: `components/ui/button.tsx`, `input.tsx`, `label.tsx`, `card.tsx` created.

- [ ] **Step 4: Verify the app builds**

Run: `cd apps/web && pnpm build`
Expected: build completes with `✓ Compiled successfully`, exit code 0.

- [ ] **Step 5: Create `apps/web/Dockerfile`**

```dockerfile
FROM node:20-alpine AS base
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
```

- [ ] **Step 6: Add the `web` service to root `docker-compose.yml`**

Add under `services:`, after `api`:

```yaml
  web:
    build: ./apps/web
    env_file: .env
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    ports:
      - "3000:3000"
    depends_on:
      - api
```

- [ ] **Step 7: Verify Docker Compose config is still valid**

Run: `docker compose config --quiet`
Expected: no output, exit code 0.

- [ ] **Step 8: Commit**

```bash
git add apps/web docker-compose.yml
git commit -m "feat(web): scaffold Next.js app with Tailwind and shadcn/ui"
```

---

### Task 12: Frontend API client and auth pages

**Files:**
- Create: `apps/web/lib/api-client.ts`
- Create: `apps/web/lib/auth.ts`
- Create: `apps/web/app/(auth)/login/page.tsx`
- Create: `apps/web/app/(auth)/register/page.tsx`

**Interfaces:**
- Produces: `apiFetch<T>(path, init) -> Promise<T>` (attaches bearer token, refreshes on `token_expired`, throws `ApiError`), `setTokens`, `clearTokens` in `lib/api-client.ts`; `register(organizationName, email, password)`, `login(email, password)`, `logout()`, `getCurrentUser() -> Promise<CurrentUser>` in `lib/auth.ts`. Later tasks (dashboard layout, leads page) depend on these.

- [ ] **Step 1: Create `apps/web/lib/api-client.ts`**

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function getTokens() {
  if (typeof window === "undefined") return { access: null as string | null, refresh: null as string | null };
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({}));
  return new ApiError(
    response.status,
    body.code ?? "unknown_error",
    body.message ?? "Something went wrong",
    body.details ?? {},
  );
}

async function refreshAccessToken(): Promise<string | null> {
  const { refresh } = getTokens();
  if (!refresh) return null;
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) return null;
  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token as string;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { access } = getTokens();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);

  let response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (response.status === 401) {
    const body = await response.clone().json().catch(() => ({}));
    if (body.code === "token_expired") {
      const newAccess = await refreshAccessToken();
      if (newAccess) {
        headers.set("Authorization", `Bearer ${newAccess}`);
        response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
      }
    }
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
```

- [ ] **Step 2: Create `apps/web/lib/auth.ts`**

```typescript
import { apiFetch, clearTokens, setTokens } from "./api-client";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  role: string;
  organization_id: string;
}

export async function register(organizationName: string, email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ organization_name: organizationName, email, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export async function login(email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export function logout(): void {
  clearTokens();
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me");
}
```

- [ ] **Step 3: Create `apps/web/app/(auth)/login/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { login } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/leads");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50">
      <Card className="w-full max-w-sm p-8">
        <h1 className="mb-6 text-xl font-semibold text-neutral-900">Sign in</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-neutral-500">
          No account?{" "}
          <a href="/register" className="font-medium text-neutral-900 underline">
            Register
          </a>
        </p>
      </Card>
    </main>
  );
}
```

- [ ] **Step 4: Create `apps/web/app/(auth)/register/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { register } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function RegisterPage() {
  const router = useRouter();
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(organizationName, email, password);
      router.push("/leads");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50">
      <Card className="w-full max-w-sm p-8">
        <h1 className="mb-6 text-xl font-semibold text-neutral-900">Create your account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="organizationName">Organization name</Label>
            <Input
              id="organizationName"
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating account..." : "Register"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-neutral-500">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-neutral-900 underline">
            Sign in
          </a>
        </p>
      </Card>
    </main>
  );
}
```

- [ ] **Step 5: Verify the app builds and type-checks**

Run: `cd apps/web && pnpm build`
Expected: `✓ Compiled successfully`, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add apps/web/lib apps/web/app/\(auth\)
git commit -m "feat(web): add API client and login/register pages"
```

---

### Task 13: Protected dashboard layout, leads page, e2e smoke test

**Files:**
- Create: `apps/web/app/(dashboard)/layout.tsx`
- Create: `apps/web/app/(dashboard)/leads/page.tsx`
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/leads.spec.ts`
- Modify: `apps/web/package.json` (add `test:e2e` script and `@playwright/test` dev dependency)

**Interfaces:**
- Consumes: `getCurrentUser`, `logout` from `lib/auth.ts`; `apiFetch` from `lib/api-client.ts` (Task 12).
- Produces: `/leads` route rendered inside a layout that redirects unauthenticated visitors to `/login`.

- [ ] **Step 1: Create `apps/web/app/(dashboard)/layout.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { type CurrentUser, getCurrentUser, logout } from "@/lib/auth";
import { Button } from "@/components/ui/button";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  if (!checked) return null;

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-6 py-4">
        <span className="font-semibold text-neutral-900">B2B Campaign</span>
        {user && (
          <div className="flex items-center gap-4">
            <span className="text-sm text-neutral-500">{user.email}</span>
            <Button
              variant="outline"
              onClick={() => {
                logout();
                router.push("/login");
              }}
            >
              Log out
            </Button>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Create `apps/web/app/(dashboard)/leads/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface Lead {
  id: string;
  contact_name: string | null;
  email: string | null;
  status: string;
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[] | null>(null);

  useEffect(() => {
    apiFetch<Lead[]>("/leads").then(setLeads);
  }, []);

  if (leads === null) {
    return <p className="text-neutral-500">Loading...</p>;
  }

  if (leads.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-12 text-center">
        <h2 className="text-lg font-medium text-neutral-900">No leads yet</h2>
        <p className="mt-2 text-sm text-neutral-500">
          Lead discovery and import are coming in the next release.
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-neutral-200 rounded-lg border border-neutral-200 bg-white">
      {leads.map((lead) => (
        <li key={lead.id} className="px-4 py-3 text-sm text-neutral-900">
          {lead.contact_name ?? lead.email ?? "Unnamed lead"} — {lead.status}
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 3: Install Playwright**

Run: `cd apps/web && pnpm add -D @playwright/test && pnpm exec playwright install --with-deps chromium`
Expected: package added to `devDependencies`; browser binaries installed.

- [ ] **Step 4: Create `apps/web/playwright.config.ts`**

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL: "http://localhost:3000",
  },
});
```

- [ ] **Step 5: Create `apps/web/e2e/leads.spec.ts`**

```typescript
import { expect, test } from "@playwright/test";

test("register and see empty leads state", async ({ page }) => {
  const email = `test-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Organization name").fill("E2E Test Org");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /register/i }).click();

  await expect(page).toHaveURL(/\/leads/);
  await expect(page.getByText("No leads yet")).toBeVisible();
});
```

- [ ] **Step 6: Add the `test:e2e` script to `apps/web/package.json`**

In the `"scripts"` block, add:

```json
"test:e2e": "playwright test"
```

- [ ] **Step 7: Run the e2e test against the full stack**

Run: `docker compose up -d && cd apps/web && pnpm test:e2e`
Expected: `1 passed`. (This requires the `api`, `db`, and `web` containers from Tasks 1–11 running; it is a manual/pre-release check, not part of the fast CI job in Task 10/14 — documented as such in the README in Task 14.)

- [ ] **Step 8: Commit**

```bash
git add apps/web/app/\(dashboard\) apps/web/playwright.config.ts apps/web/e2e apps/web/package.json
git commit -m "feat(web): add protected dashboard layout, leads page, and e2e smoke test"
```

---

### Task 14: Frontend CI job and final README

**Files:**
- Modify: `.github/workflows/ci.yml` (add `web` job)
- Modify: `README.md`

**Interfaces:**
- Produces: complete CI (`api` + `web` jobs) and a README covering setup, configuration, running the stack, running tests, and project structure.

- [ ] **Step 1: Append the `web` job to `.github/workflows/ci.yml`**

Add this job after the existing `api` job (same indentation level, under `jobs:`):

```yaml
  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          cache-dependency-path: apps/web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm build
```

- [ ] **Step 2: Verify the workflow YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` (from repo root)
Expected: no errors, exit code 0.

- [ ] **Step 3: Replace `README.md` with the full setup guide**

```markdown
# B2B Lead Discovery & Outreach Platform

Automates B2B lead discovery, qualification, AI-personalized outreach, and
email campaign sending, with a CRM layer on top. See
`docs/superpowers/specs/2026-07-23-foundation-design.md` for the full
program design and sub-project roadmap.

This repository currently implements the **Foundation** sub-project: auth,
the core data model (organizations, users, companies, leads), and the
Docker dev environment that later sub-projects (lead discovery, AI
personalization, email campaigns, dashboard, CRM) build on.

## Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python dependency manager)
- [pnpm](https://pnpm.io/) and Node.js 20+

## Setup

1. Copy the environment template and fill in secrets:

   ```bash
   cp .env.example .env
   ```

   At minimum, set `SECRET_KEY` to a random string. `GOOGLE_CLIENT_ID` /
   `NEXT_PUBLIC_GOOGLE_CLIENT_ID` are only needed if you enable Google
   sign-in.

2. Start Postgres and Redis:

   ```bash
   docker compose up -d db redis
   ```

3. Install backend dependencies and run migrations:

   ```bash
   cd apps/api
   uv sync
   uv run alembic upgrade head
   ```

4. Install frontend dependencies:

   ```bash
   cd apps/web
   pnpm install
   ```

5. Run the full stack:

   ```bash
   docker compose up --build
   ```

   - API: http://localhost:8000 (interactive docs at `/docs`)
   - Web: http://localhost:3000

## Running tests

Backend (in-memory SQLite, no external services needed):

```bash
cd apps/api
uv run pytest -v
```

Frontend build/lint check:

```bash
cd apps/web
pnpm lint
pnpm build
```

Frontend end-to-end smoke test (requires the full stack running via
`docker compose up`):

```bash
cd apps/web
pnpm test:e2e
```

## Project structure

```
apps/
  api/   FastAPI backend (SQLAlchemy, Alembic, JWT + Google OAuth, REST API)
  web/   Next.js frontend (TypeScript, Tailwind, shadcn/ui)
docs/
  superpowers/specs/   Design specs, one per sub-project
  superpowers/plans/   Implementation plans, one per sub-project
```

## Compliance

Lead sourcing and email sending features (added in later sub-projects)
are required to respect target sites' robots.txt/ToS, maintain a
suppression list, honor unsubscribe/opt-out requests, and avoid
harvesting personal data from sources that prohibit automated access.
See the design spec for details.
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "docs: finalize README and add frontend CI job"
```

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

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

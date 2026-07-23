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

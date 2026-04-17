from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from .config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "typ": token_type})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(data, delta, token_type="access")


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, str, datetime]:
    delta = expires_delta or timedelta(minutes=settings.refresh_token_expire_minutes)
    jti = str(uuid4())
    expire = datetime.utcnow() + delta
    token = _create_token({**data, "jti": jti}, delta, token_type="refresh")
    return token, jti, expire


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    token_type = payload.get("typ")
    if token_type != expected_type:
        raise InvalidTokenError("Invalid token type")
    return payload



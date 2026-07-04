"""
A working JWT auth flow so the app runs standalone in dev. The thesis's tech stack
names Auth0 for production role-based access control — swap `create_access_token` /
`decode_access_token` for an Auth0 SDK call and this module's public interface
(`get_current_user` dependency) shouldn't need to change in the routers.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .database import get_db
from .models import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)
COOKIE_NAME = "meetmind_token"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: DBSession = Depends(get_db),
) -> User:
    """
    Accepts either an `Authorization: Bearer <token>` header OR the httpOnly
    `meetmind_token` cookie (set by /auth/login and /auth/register when
    USE_COOKIE_AUTH=true) — whichever is present. The cookie is what the web
    frontend should rely on going forward (not readable by JS, so it isn't exposed
    to XSS the way a token sitting in localStorage would be); the bearer header stays
    supported for API clients, scripts, and backward compatibility.
    """
    token = None
    if credentials is not None:
        token = credentials.credentials
    elif COOKIE_NAME in request.cookies:
        token = request.cookies[COOKIE_NAME]

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

"""Authentication and authorization utilities for the fitness tracking API."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User

# ---------------------------------------------------------------------------
# Authentication configuration
# ---------------------------------------------------------------------------

MIN_SECRET_KEY_LENGTH = 32

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is not set.")
if len(JWT_SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
    raise RuntimeError(
        f"JWT_SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long."
    )

# The signing algorithm is fixed in code rather than read from the
# environment, so a misconfiguration cannot weaken token verification.
JWT_ALGORITHM = "HS256"


def _read_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment, failing with a clear error."""
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer.") from None
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


ACCESS_TOKEN_EXPIRE_MINUTES = _read_positive_int_env(
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    60,
)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

password_hasher = PasswordHash.recommended()

# Verified against when a username does not exist, so that login takes
# roughly the same time whether or not the account exists.
_DUMMY_PASSWORD_HASH = password_hasher.hash("timing-attack-mitigation")


def hash_password(password: str) -> str:
    """Hash a plaintext password before storing it in the database."""
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a plaintext password against its stored password hash."""
    return password_hasher.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT authentication
# ---------------------------------------------------------------------------

# Relative URL (no leading slash) so docs keep working behind a path prefix.
# Must match the real login route.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def create_access_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for an authenticated user."""

    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# User authentication
# ---------------------------------------------------------------------------


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    """Authenticate a user by username and password.

    Returns None for both unknown usernames and wrong passwords, and spends
    comparable time in either case to avoid revealing which usernames exist.
    """

    user = db.scalar(select(User).where(User.username == username))

    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from a JWT access token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise credentials_exception from exc

    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Ownership authorization
# ---------------------------------------------------------------------------


def verify_resource_owner(
    resource_user_id: int,
    current_user: User,
) -> None:
    """Ensure the authenticated user owns the requested resource."""

    if resource_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
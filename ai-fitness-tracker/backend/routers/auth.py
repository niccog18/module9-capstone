from typing import Annotated

from auth import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    hash_password,
)
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from models import User
from schemas import TokenResponse, UserCreate, UserResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserCreate,
    db: DatabaseSession,
) -> User:
    """Create a new user account."""

    # Emails are stored lowercase so uniqueness is case-insensitive.
    email = str(user_data.email).lower()

    existing_user = db.scalar(
        select(User).where(
            (User.username == user_data.username) | (User.email == email)
        )
    )

    if existing_user is not None:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already registered.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    user = User(
        username=user_data.username,
        email=email,
        password_hash=hash_password(user_data.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered.",
        ) from exc

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DatabaseSession,
) -> TokenResponse:
    """Authenticate a user and return a JWT access token.

    Credentials are sent as form data (``username`` and ``password``) so the
    Swagger "Authorize" button works.
    """

    user = authenticate_user(
        db,
        form_data.username,
        form_data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token lifetime comes from ACCESS_TOKEN_EXPIRE_MINUTES (see auth.py).
    access_token = create_access_token(user.user_id)

    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
)
def read_current_user(
    current_user: CurrentUser,
) -> User:
    """Return the authenticated user's account information."""

    return current_user

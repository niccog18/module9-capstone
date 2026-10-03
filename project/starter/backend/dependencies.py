"""Shared FastAPI dependencies, query parameters and lookup helpers.

Routers import from this module instead of from main.py, which avoids
circular imports and keeps each ownership rule defined in exactly one place.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import Exercise, User

DatabaseSession = Annotated[Session, Depends(get_db)]

Limit = Annotated[
    int,
    Query(ge=1, le=500, description="Maximum number of items to return."),
]
Offset = Annotated[
    int,
    Query(ge=0, description="Number of items to skip."),
]


# ---------------------------------------------------------------------------
# Exercise lookup helpers
# ---------------------------------------------------------------------------
#
# Resources owned by another user are reported as 404 rather than 403 so the
# API does not reveal which IDs exist.


def get_visible_exercise_or_404(
    db: Session,
    exercise_id: int,
    current_user: User,
) -> Exercise:
    """Return a system exercise or one of the user's custom exercises.

    Other users' custom exercises are reported as 404.
    """

    exercise = db.scalar(
        select(Exercise).where(
            Exercise.exercise_id == exercise_id,
            or_(
                Exercise.user_id.is_(None),
                Exercise.user_id == current_user.user_id,
            ),
        )
    )

    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found.",
        )

    return exercise


def get_owned_exercise_or_404(
    db: Session,
    exercise_id: int,
    current_user: User,
) -> Exercise:
    """Return a custom exercise the user may modify.

    System exercises are visible but read-only (403). Other users' custom
    exercises are reported as 404.
    """

    exercise = get_visible_exercise_or_404(db, exercise_id, current_user)

    if exercise.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System exercises cannot be modified.",
        )

    return exercise
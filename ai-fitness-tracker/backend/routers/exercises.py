"""Exercise endpoints: the shared system library plus user-owned custom exercises.

System exercises (user_id is null) are visible to everyone and read-only
through the API. Custom exercises are owned by the user who created them.
"""

from auth import CurrentUser
from dependencies import (
    DatabaseSession,
    Limit,
    Offset,
    get_owned_exercise_or_404,
    get_visible_exercise_or_404,
)
from fastapi import APIRouter, HTTPException, status
from models import Exercise
from schemas import ExerciseCreate, ExerciseResponse, ExerciseUpdate
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/exercises",
    tags=["Exercises"],
)


@router.get(
    "",
    response_model=list[ExerciseResponse],
)
def get_exercises(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[Exercise]:
    """Return system exercises plus the authenticated user's custom exercises."""

    statement = (
        select(Exercise)
        .where(
            or_(
                Exercise.user_id.is_(None),
                Exercise.user_id == current_user.user_id,
            )
        )
        .order_by(Exercise.name, Exercise.exercise_id)
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{exercise_id}",
    response_model=ExerciseResponse,
)
def get_exercise(
    exercise_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Exercise:
    """Return a system exercise or one of the user's custom exercises."""

    return get_visible_exercise_or_404(db, exercise_id, current_user)


@router.post(
    "",
    response_model=ExerciseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise(
    exercise_data: ExerciseCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Exercise:
    """Create a custom exercise owned by the authenticated user."""

    exercise = Exercise(
        user_id=current_user.user_id,
        name=exercise_data.name,
        muscle_group=exercise_data.muscle_group,
        equipment=exercise_data.equipment,
        description=exercise_data.description,
    )

    db.add(exercise)

    try:
        db.commit()
        db.refresh(exercise)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an exercise with this name.",
        ) from exc

    return exercise


@router.patch(
    "/{exercise_id}",
    response_model=ExerciseResponse,
)
def update_exercise(
    exercise_id: int,
    exercise_data: ExerciseUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Exercise:
    """Partially update a custom exercise owned by the authenticated user.

    Only the fields included in the request body are changed.
    """

    exercise = get_owned_exercise_or_404(db, exercise_id, current_user)

    update_data = exercise_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(exercise, field_name, value)

    try:
        db.commit()
        db.refresh(exercise)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an exercise with this name.",
        ) from exc

    return exercise


@router.delete(
    "/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_exercise(
    exercise_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Delete a custom exercise that is not used in any workout or plan."""

    exercise = get_owned_exercise_or_404(db, exercise_id, current_user)

    db.delete(exercise)

    # The workout_exercises.exercise_id foreign key is ON DELETE RESTRICT,
    # so the database rejects the delete atomically if the exercise is used.
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Exercise cannot be deleted because it is used in "
                "one or more workouts or plans."
            ),
        ) from exc

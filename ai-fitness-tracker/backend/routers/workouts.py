from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth import CurrentUser
from dependencies import DatabaseSession, get_visible_exercise_or_404
from models import User, Workout, WorkoutExercise
from schemas import (
    WorkoutCreate,
    WorkoutDetailResponse,
    WorkoutExerciseCreate,
    WorkoutExerciseResponse,
    WorkoutExerciseUpdate,
    WorkoutResponse,
    WorkoutUpdate,
)

router = APIRouter(
    prefix="/workouts",
    tags=["Workouts"],
)

# ---------------------------------------------------------------------------
# Ownership lookup helpers
# ---------------------------------------------------------------------------


def get_owned_workout_or_404(
    db: Session,
    workout_id: int,
    current_user: User,
) -> Workout:
    """Return a workout owned by the user, or raise 404."""

    workout = db.scalar(
        select(Workout).where(
            Workout.workout_id == workout_id,
            Workout.user_id == current_user.user_id,
        )
    )

    if workout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found.",
        )

    return workout


def get_workout_exercise_or_404(
    db: Session,
    workout_id: int,
    workout_exercise_id: int,
) -> WorkoutExercise:
    """Return an exercise entry within a workout, or raise 404.

    The caller must already have verified ownership of the workout.
    """

    workout_exercise = db.scalar(
        select(WorkoutExercise)
        .options(selectinload(WorkoutExercise.exercise))
        .where(
            WorkoutExercise.workout_id == workout_id,
            WorkoutExercise.workout_exercise_id == workout_exercise_id,
        )
    )

    if workout_exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise entry not found in this workout.",
        )

    return workout_exercise


# ---------------------------------------------------------------------------
# Workout endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=WorkoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workout(
    workout_data: WorkoutCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Workout:
    """Create a workout owned by the authenticated user."""

    workout = Workout(
        user_id=current_user.user_id,
        workout_date=workout_data.workout_date,
        duration_minutes=workout_data.duration_minutes,
        notes=workout_data.notes,
    )

    db.add(workout)
    db.commit()
    db.refresh(workout)

    return workout


@router.get(
    "",
    response_model=list[WorkoutResponse],
)
def get_workouts(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Workout]:
    """Return the authenticated user's workouts, newest first."""

    statement = (
        select(Workout)
        .where(Workout.user_id == current_user.user_id)
        .order_by(
            Workout.workout_date.desc(),
            Workout.workout_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{workout_id}",
    response_model=WorkoutDetailResponse,
)
def get_workout(
    workout_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Workout:
    """Return one workout with its exercises."""

    statement = (
        select(Workout)
        .options(
            selectinload(Workout.workout_exercises).selectinload(
                WorkoutExercise.exercise
            )
        )
        .where(
            Workout.workout_id == workout_id,
            Workout.user_id == current_user.user_id,
        )
    )

    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout not found.",
        )

    return workout


@router.patch(
    "/{workout_id}",
    response_model=WorkoutResponse,
)
def update_workout(
    workout_id: int,
    workout_data: WorkoutUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Workout:
    """Update a workout owned by the authenticated user.

    Only the fields included in the request body are changed.
    """

    workout = get_owned_workout_or_404(db, workout_id, current_user)

    update_data = workout_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(workout, field_name, value)

    db.commit()
    db.refresh(workout)

    return workout


@router.delete(
    "/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_workout(
    workout_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Delete a workout owned by the authenticated user."""

    workout = get_owned_workout_or_404(db, workout_id, current_user)

    db.delete(workout)
    db.commit()


# ---------------------------------------------------------------------------
# Workout exercise endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{workout_id}/exercises",
    response_model=WorkoutExerciseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Workout Exercises"],
)
def add_exercise_to_workout(
    workout_id: int,
    exercise_data: WorkoutExerciseCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> WorkoutExercise:
    """Add an exercise performance record to a user's workout."""

    get_owned_workout_or_404(db, workout_id, current_user)

    get_visible_exercise_or_404(
        db,
        exercise_data.exercise_id,
        current_user,
    )

    workout_exercise = WorkoutExercise(
        workout_id=workout_id,
        exercise_id=exercise_data.exercise_id,
        position=exercise_data.position,
        sets=exercise_data.sets,
        reps=exercise_data.reps,
        weight=exercise_data.weight,
        duration_seconds=exercise_data.duration_seconds,
        distance_miles=exercise_data.distance_miles,
    )

    db.add(workout_exercise)
    db.commit()
    db.refresh(workout_exercise)

    return workout_exercise


@router.get(
    "/{workout_id}/exercises",
    response_model=list[WorkoutExerciseResponse],
    tags=["Workout Exercises"],
)
def get_workout_exercises(
    workout_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[WorkoutExercise]:
    """Return exercises performed during a user's workout."""

    get_owned_workout_or_404(db, workout_id, current_user)

    statement = (
        select(WorkoutExercise)
        .options(selectinload(WorkoutExercise.exercise))
        .where(WorkoutExercise.workout_id == workout_id)
        .order_by(
            WorkoutExercise.position,
            WorkoutExercise.workout_exercise_id,
        )
    )

    return list(db.scalars(statement).all())


@router.patch(
    "/{workout_id}/exercises/{workout_exercise_id}",
    response_model=WorkoutExerciseResponse,
    tags=["Workout Exercises"],
)
def update_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
    exercise_data: WorkoutExerciseUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> WorkoutExercise:
    """Update exercise performance within a user's workout.

    Only the fields included in the request body are changed.
    """

    get_owned_workout_or_404(db, workout_id, current_user)

    workout_exercise = get_workout_exercise_or_404(
        db,
        workout_id,
        workout_exercise_id,
    )

    update_data = exercise_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(workout_exercise, field_name, value)

    db.commit()
    db.refresh(workout_exercise)

    return workout_exercise


@router.delete(
    "/{workout_id}/exercises/{workout_exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Workout Exercises"],
)
def delete_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Remove an exercise entry from a user's workout."""

    get_owned_workout_or_404(db, workout_id, current_user)

    workout_exercise = get_workout_exercise_or_404(
        db,
        workout_id,
        workout_exercise_id,
    )

    db.delete(workout_exercise)
    db.commit()
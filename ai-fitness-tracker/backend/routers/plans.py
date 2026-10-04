"""Plan endpoints: workout plans, their sessions and prescribed exercises.

A plan contains sessions; each session contains prescribed exercises (the
training prescription, as opposed to the completed WorkoutExercise log).
"""

from auth import CurrentUser
from dependencies import (
    DatabaseSession,
    Limit,
    Offset,
    get_visible_exercise_or_404,
)
from fastapi import APIRouter, HTTPException, status
from models import PlanExercise, PlanSession, User, WorkoutPlan
from schemas import (
    PlanExerciseCreate,
    PlanExerciseResponse,
    PlanExerciseUpdate,
    PlanSessionCreate,
    PlanSessionDetailResponse,
    PlanSessionResponse,
    PlanSessionUpdate,
    WorkoutPlanCreate,
    WorkoutPlanDetailResponse,
    WorkoutPlanResponse,
    WorkoutPlanUpdate,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

# Each route carries its own tag (Workout Plans / Plan Sessions / Training
# Prescriptions), so the router itself has none.
router = APIRouter(prefix="/plans")


# ---------------------------------------------------------------------------
# Ownership lookup helpers
# ---------------------------------------------------------------------------
#
# Resources owned by another user are reported as 404 rather than 403 so the
# API does not reveal which IDs exist.


def get_owned_plan_or_404(
    db: Session,
    plan_id: int,
    current_user: User,
) -> WorkoutPlan:
    """Return a workout plan owned by the user, or raise 404."""

    plan = db.scalar(
        select(WorkoutPlan).where(
            WorkoutPlan.plan_id == plan_id,
            WorkoutPlan.user_id == current_user.user_id,
        )
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found.",
        )

    return plan


def get_owned_session_or_404(
    db: Session,
    plan_id: int,
    session_id: int,
    current_user: User,
) -> PlanSession:
    """Return a session of a plan owned by the user, or raise 404."""

    plan_session = db.scalar(
        select(PlanSession)
        .join(WorkoutPlan, PlanSession.plan_id == WorkoutPlan.plan_id)
        .where(
            PlanSession.session_id == session_id,
            PlanSession.plan_id == plan_id,
            WorkoutPlan.user_id == current_user.user_id,
        )
    )

    if plan_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan session not found.",
        )

    return plan_session


def get_plan_exercise_or_404(
    db: Session,
    session_id: int,
    plan_exercise_id: int,
) -> PlanExercise:
    """Return a prescribed exercise within a session, or raise 404.

    The caller must already have verified ownership of the session.
    """

    plan_exercise = db.scalar(
        select(PlanExercise)
        .options(selectinload(PlanExercise.exercise))
        .where(
            PlanExercise.session_id == session_id,
            PlanExercise.plan_exercise_id == plan_exercise_id,
        )
    )

    if plan_exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescribed exercise not found in this session.",
        )

    return plan_exercise


# ---------------------------------------------------------------------------
# Workout plan endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[WorkoutPlanResponse],
    tags=["Workout Plans"],
)
def get_workout_plans(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[WorkoutPlan]:
    """Return the authenticated user's workout plans, newest first."""

    statement = (
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.user_id)
        .order_by(
            WorkoutPlan.created_at.desc(),
            WorkoutPlan.plan_id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{plan_id}",
    response_model=WorkoutPlanDetailResponse,
    tags=["Workout Plans"],
)
def get_workout_plan(
    plan_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> WorkoutPlan:
    """Return one workout plan with its sessions and prescribed exercises."""

    statement = (
        select(WorkoutPlan)
        .options(
            selectinload(WorkoutPlan.sessions)
            .selectinload(PlanSession.exercises)
            .selectinload(PlanExercise.exercise)
        )
        .where(
            WorkoutPlan.plan_id == plan_id,
            WorkoutPlan.user_id == current_user.user_id,
        )
    )

    plan = db.scalar(statement)

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan not found.",
        )

    return plan


@router.post(
    "",
    response_model=WorkoutPlanResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Workout Plans"],
)
def create_workout_plan(
    plan_data: WorkoutPlanCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> WorkoutPlan:
    """Create a workout plan owned by the authenticated user."""

    plan = WorkoutPlan(
        user_id=current_user.user_id,
        plan_name=plan_data.plan_name,
        goal=plan_data.goal,
    )

    db.add(plan)

    try:
        db.commit()
        db.refresh(plan)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a workout plan with this name.",
        ) from exc

    return plan


@router.patch(
    "/{plan_id}",
    response_model=WorkoutPlanResponse,
    tags=["Workout Plans"],
)
def update_workout_plan(
    plan_id: int,
    plan_data: WorkoutPlanUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> WorkoutPlan:
    """Update a workout plan owned by the authenticated user.

    Only the fields included in the request body are changed.
    """

    plan = get_owned_plan_or_404(db, plan_id, current_user)

    update_data = plan_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(plan, field_name, value)

    try:
        db.commit()
        db.refresh(plan)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a workout plan with this name.",
        ) from exc

    return plan


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Workout Plans"],
)
def delete_workout_plan(
    plan_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Delete a workout plan owned by the authenticated user."""

    plan = get_owned_plan_or_404(db, plan_id, current_user)

    db.delete(plan)
    db.commit()


# ---------------------------------------------------------------------------
# Plan session endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{plan_id}/sessions",
    response_model=PlanSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Plan Sessions"],
)
def create_plan_session(
    plan_id: int,
    session_data: PlanSessionCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlanSession:
    """Add a training session to a workout plan owned by the user."""

    get_owned_plan_or_404(db, plan_id, current_user)

    plan_session = PlanSession(
        plan_id=plan_id,
        session_name=session_data.session_name,
        position=session_data.position,
        notes=session_data.notes,
    )

    db.add(plan_session)
    db.commit()
    db.refresh(plan_session)

    return plan_session


@router.get(
    "/{plan_id}/sessions",
    response_model=list[PlanSessionResponse],
    tags=["Plan Sessions"],
)
def get_plan_sessions(
    plan_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[PlanSession]:
    """Return the sessions of a workout plan owned by the user."""

    get_owned_plan_or_404(db, plan_id, current_user)

    statement = (
        select(PlanSession)
        .where(PlanSession.plan_id == plan_id)
        .order_by(PlanSession.position, PlanSession.session_id)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{plan_id}/sessions/{session_id}",
    response_model=PlanSessionDetailResponse,
    tags=["Plan Sessions"],
)
def get_plan_session(
    plan_id: int,
    session_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlanSession:
    """Return one plan session with its prescribed exercises."""

    plan_session = get_owned_session_or_404(
        db,
        plan_id,
        session_id,
        current_user,
    )

    statement = (
        select(PlanSession)
        .options(
            selectinload(PlanSession.exercises).selectinload(PlanExercise.exercise)
        )
        .where(PlanSession.session_id == plan_session.session_id)
    )

    return db.scalars(statement).one()


@router.patch(
    "/{plan_id}/sessions/{session_id}",
    response_model=PlanSessionResponse,
    tags=["Plan Sessions"],
)
def update_plan_session(
    plan_id: int,
    session_id: int,
    session_data: PlanSessionUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlanSession:
    """Partially update a plan session.

    Only the fields included in the request body are changed.
    """

    plan_session = get_owned_session_or_404(
        db,
        plan_id,
        session_id,
        current_user,
    )

    update_data = session_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(plan_session, field_name, value)

    db.commit()
    db.refresh(plan_session)

    return plan_session


@router.delete(
    "/{plan_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Plan Sessions"],
)
def delete_plan_session(
    plan_id: int,
    session_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Delete a plan session and its prescribed exercises."""

    plan_session = get_owned_session_or_404(
        db,
        plan_id,
        session_id,
        current_user,
    )

    db.delete(plan_session)
    db.commit()


# ---------------------------------------------------------------------------
# Training prescription endpoints (prescribed exercises)
# ---------------------------------------------------------------------------


@router.post(
    "/{plan_id}/sessions/{session_id}/exercises",
    response_model=PlanExerciseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Training Prescriptions"],
)
def add_exercise_to_session(
    plan_id: int,
    session_id: int,
    exercise_data: PlanExerciseCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlanExercise:
    """Prescribe an exercise within a plan session.

    The exercise must be a system exercise or one of the user's own custom
    exercises.
    """

    get_owned_session_or_404(db, plan_id, session_id, current_user)
    get_visible_exercise_or_404(db, exercise_data.exercise_id, current_user)

    plan_exercise = PlanExercise(
        session_id=session_id,
        **exercise_data.model_dump(),
    )

    db.add(plan_exercise)
    db.commit()
    db.refresh(plan_exercise)

    return plan_exercise


@router.get(
    "/{plan_id}/sessions/{session_id}/exercises",
    response_model=list[PlanExerciseResponse],
    tags=["Training Prescriptions"],
)
def get_session_exercises(
    plan_id: int,
    session_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[PlanExercise]:
    """Return the prescribed exercises of a plan session."""

    get_owned_session_or_404(db, plan_id, session_id, current_user)

    statement = (
        select(PlanExercise)
        .options(selectinload(PlanExercise.exercise))
        .where(PlanExercise.session_id == session_id)
        .order_by(PlanExercise.position, PlanExercise.plan_exercise_id)
    )

    return list(db.scalars(statement).all())


@router.patch(
    "/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
    response_model=PlanExerciseResponse,
    tags=["Training Prescriptions"],
)
def update_session_exercise(
    plan_id: int,
    session_id: int,
    plan_exercise_id: int,
    exercise_data: PlanExerciseUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> PlanExercise:
    """Partially update a prescribed exercise.

    Only the fields included in the request body are changed. The resulting
    rep range must still satisfy ``reps_max >= reps_min``.
    """

    get_owned_session_or_404(db, plan_id, session_id, current_user)

    plan_exercise = get_plan_exercise_or_404(
        db,
        session_id,
        plan_exercise_id,
    )

    update_data = exercise_data.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(plan_exercise, field_name, value)

    if plan_exercise.reps_max < plan_exercise.reps_min:
        db.rollback()
        raise HTTPException(
            status_code=422,  # literal: the status constant was renamed across Starlette versions
            detail="reps_max must be greater than or equal to reps_min.",
        )

    db.commit()
    db.refresh(plan_exercise)

    return plan_exercise


@router.delete(
    "/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Training Prescriptions"],
)
def delete_session_exercise(
    plan_id: int,
    session_id: int,
    plan_exercise_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> None:
    """Remove a prescribed exercise from a plan session."""

    get_owned_session_or_404(db, plan_id, session_id, current_user)

    plan_exercise = get_plan_exercise_or_404(
        db,
        session_id,
        plan_exercise_id,
    )

    db.delete(plan_exercise)
    db.commit()

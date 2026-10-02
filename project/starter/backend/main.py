"""FastAPI application and API endpoints for the fitness tracking application."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from auth import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    hash_password,
)
from database import Base, engine, get_db
from models import (
    Exercise,
    PlanExercise,
    PlanSession,
    User,
    Workout,
    WorkoutExercise,
    WorkoutPlan,
)
from schemas import (
    ExerciseCreate,
    ExerciseResponse,
    ExerciseUpdate,
    HealthResponse,
    PlanExerciseCreate,
    PlanExerciseResponse,
    PlanExerciseUpdate,
    PlanSessionCreate,
    PlanSessionDetailResponse,
    PlanSessionResponse,
    PlanSessionUpdate,
    TokenResponse,
    UserCreate,
    UserResponse,
    WorkoutCreate,
    WorkoutDetailResponse,
    WorkoutExerciseCreate,
    WorkoutExerciseResponse,
    WorkoutExerciseUpdate,
    WorkoutPlanCreate,
    WorkoutPlanDetailResponse,
    WorkoutPlanResponse,
    WorkoutPlanUpdate,
    WorkoutResponse,
    WorkoutUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
    if origin.strip()
]


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources.

    Table creation is intended for development. Use Alembic migrations in
    production.
    """

    Base.metadata.create_all(bind=engine)

    yield


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Fitness Tracker API",
    description=(
        "A professional fitness tracking API for managing workouts, "
        "exercises, workout plans, authentication, and AI-assisted fitness "
        "information."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Authentication uses a bearer token in the Authorization header, not
# cookies, so credentialed cross-origin requests are not needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Dependency aliases and shared query parameters
# ---------------------------------------------------------------------------


DatabaseSession = Annotated[Session, Depends(get_db)]

Limit = Annotated[
    int,
    Query(ge=1, le=500, description="Maximum number of items to return."),
]
Offset = Annotated[
    int,
    Query(ge=0, description="Number of items to skip."),
]

# All versioned API routes hang off this router; only the root and health
# endpoints live outside /api/v1.
router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Ownership lookup helpers
# ---------------------------------------------------------------------------
#
# Resources owned by another user are reported as 404 rather than 403 so the
# API does not reveal which IDs exist.


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
# Root and health endpoints
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
def read_root() -> dict[str, str]:
    """Return basic API information."""

    return {
        "name": "Fitness Tracker API",
        "version": app.version,
        "status": "running",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
)
def health_check(
    response: Response,
    db: DatabaseSession,
) -> HealthResponse:
    """Check whether the API and database are available.

    Returns 503 when the database is unreachable so load balancers and
    orchestrators can detect an unhealthy instance.
    """

    try:
        db.execute(select(1))
        database_status = "healthy"
    except SQLAlchemyError:
        logger.exception("Database health check failed.")
        database_status = "unhealthy"

    if database_status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=database_status,
        database=database_status,
        ollama="not_checked",
        chromadb="not_checked",
    )


# ---------------------------------------------------------------------------
# Authentication endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
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
    "/auth/login",
    response_model=TokenResponse,
    tags=["Authentication"],
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
    "/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
)
def read_current_user(
    current_user: CurrentUser,
) -> User:
    """Return the authenticated user's account information."""

    return current_user


# ---------------------------------------------------------------------------
# Workout endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/workouts",
    response_model=WorkoutResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Workouts"],
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
    "/workouts",
    response_model=list[WorkoutResponse],
    tags=["Workouts"],
)
def get_workouts(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: Limit = 100,
    offset: Offset = 0,
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
    "/workouts/{workout_id}",
    response_model=WorkoutDetailResponse,
    tags=["Workouts"],
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
    "/workouts/{workout_id}",
    response_model=WorkoutResponse,
    tags=["Workouts"],
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
    "/workouts/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Workouts"],
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
# Exercise endpoints
# ---------------------------------------------------------------------------
#
# Exercises are either system exercises (user_id is null: the shared library,
# read-only here) or custom exercises owned by the user who created them.


@router.get(
    "/exercises",
    response_model=list[ExerciseResponse],
    tags=["Exercises"],
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
    "/exercises/{exercise_id}",
    response_model=ExerciseResponse,
    tags=["Exercises"],
)
def get_exercise(
    exercise_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Exercise:
    """Return a system exercise or one of the user's custom exercises."""

    return get_visible_exercise_or_404(db, exercise_id, current_user)


@router.post(
    "/exercises",
    response_model=ExerciseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Exercises"],
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
    "/exercises/{exercise_id}",
    response_model=ExerciseResponse,
    tags=["Exercises"],
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
    "/exercises/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Exercises"],
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


# ---------------------------------------------------------------------------
# Workout exercise endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/workouts/{workout_id}/exercises",
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

    get_visible_exercise_or_404(db, exercise_data.exercise_id, current_user)

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
    "/workouts/{workout_id}/exercises",
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
    "/workouts/{workout_id}/exercises/{workout_exercise_id}",
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
    "/workouts/{workout_id}/exercises/{workout_exercise_id}",
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


# ---------------------------------------------------------------------------
# Workout plan endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
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
    "/plans/{plan_id}",
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
    "/plans",
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
    "/plans/{plan_id}",
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
    "/plans/{plan_id}",
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
    "/plans/{plan_id}/sessions",
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
    "/plans/{plan_id}/sessions",
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
    "/plans/{plan_id}/sessions/{session_id}",
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
            selectinload(PlanSession.exercises).selectinload(
                PlanExercise.exercise
            )
        )
        .where(PlanSession.session_id == plan_session.session_id)
    )

    return db.scalars(statement).one()


@router.patch(
    "/plans/{plan_id}/sessions/{session_id}",
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
    "/plans/{plan_id}/sessions/{session_id}",
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
    "/plans/{plan_id}/sessions/{session_id}/exercises",
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
    "/plans/{plan_id}/sessions/{session_id}/exercises",
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
    "/plans/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reps_max must be greater than or equal to reps_min.",
        )

    db.commit()
    db.refresh(plan_exercise)

    return plan_exercise


@router.delete(
    "/plans/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
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


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(router)
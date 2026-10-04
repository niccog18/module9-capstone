"""Pydantic request and response schemas for the fitness tracking API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)
from typing_extensions import Self

# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


class RequestModel(BaseModel):
    """Base class for request bodies.

    Strips surrounding whitespace from strings and rejects unknown fields so
    that client typos fail loudly instead of being silently ignored.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class PartialUpdateModel(RequestModel):
    """Base class for PATCH-style update bodies.

    Guarantees that:
    - at least one field is provided, and
    - fields that map to NOT NULL columns are never explicitly set to null.

    Services should apply updates with ``model_dump(exclude_unset=True)``.
    """

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def validate_partial_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field_name in self.model_fields_set & self.non_nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Request schema for creating a user account."""

    model_config = ConfigDict(extra="forbid")

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=50,
            pattern=r"^[A-Za-z0-9_.-]+$",
        ),
    ]
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


class UserResponse(BaseModel):
    """Response schema for a user account."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Authentication schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """JWT authentication response."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


# ---------------------------------------------------------------------------
# Exercise schemas
# ---------------------------------------------------------------------------


class ExerciseCreate(RequestModel):
    """Request schema for creating an exercise."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    muscle_group: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    equipment: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )


class ExerciseUpdate(PartialUpdateModel):
    """Request schema for updating an exercise."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"name", "muscle_group", "equipment"}
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    muscle_group: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    equipment: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )


class ExerciseResponse(BaseModel):
    """Response schema for an exercise."""

    model_config = ConfigDict(from_attributes=True)

    exercise_id: int
    user_id: int | None = Field(
        description="Owner of a custom exercise; null for system exercises.",
    )
    name: str
    muscle_group: str
    equipment: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Workout exercise schemas
# ---------------------------------------------------------------------------


class WorkoutExerciseCreate(RequestModel):
    """Request schema for adding an exercise to a workout."""

    exercise_id: int = Field(
        ...,
        gt=0,
    )
    position: int = Field(
        default=0,
        ge=0,
        le=1000,
    )
    sets: int = Field(
        ...,
        gt=0,
        le=100,
    )
    reps: int = Field(
        ...,
        gt=0,
        le=1000,
    )
    weight: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    duration_seconds: int | None = Field(
        default=None,
        gt=0,
        le=86_400,
    )
    distance_miles: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class WorkoutExerciseUpdate(PartialUpdateModel):
    """Request schema for updating exercise performance in a workout."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"position", "sets", "reps"}
    )

    position: int | None = Field(
        default=None,
        ge=0,
        le=1000,
    )
    sets: int | None = Field(
        default=None,
        gt=0,
        le=100,
    )
    reps: int | None = Field(
        default=None,
        gt=0,
        le=1000,
    )
    weight: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    duration_seconds: int | None = Field(
        default=None,
        gt=0,
        le=86_400,
    )
    distance_miles: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class WorkoutExerciseResponse(BaseModel):
    """Response schema for an exercise performed in a workout."""

    model_config = ConfigDict(from_attributes=True)

    workout_exercise_id: int
    workout_id: int
    exercise_id: int
    position: int
    sets: int
    reps: int
    weight: Decimal | None
    duration_seconds: int | None
    distance_miles: Decimal | None
    exercise: ExerciseResponse


# ---------------------------------------------------------------------------
# Workout schemas
# ---------------------------------------------------------------------------


class WorkoutCreate(RequestModel):
    """Request schema for creating a workout."""

    workout_date: date
    duration_minutes: int = Field(
        ...,
        gt=0,
        le=1440,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class WorkoutUpdate(PartialUpdateModel):
    """Request schema for updating a workout."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"workout_date", "duration_minutes"}
    )

    workout_date: date | None = None
    duration_minutes: int | None = Field(
        default=None,
        gt=0,
        le=1440,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class WorkoutResponse(BaseModel):
    """Response schema for a workout without nested exercises."""

    model_config = ConfigDict(from_attributes=True)

    workout_id: int
    user_id: int
    workout_date: date
    duration_minutes: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WorkoutDetailResponse(WorkoutResponse):
    """Detailed workout response including performed exercises.

    The ORM relationship is named ``workout_exercises``; the API exposes it
    as ``exercises``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    exercises: list[WorkoutExerciseResponse] = Field(
        default_factory=list,
        validation_alias="workout_exercises",
    )


# ---------------------------------------------------------------------------
# Workout plan schemas
# ---------------------------------------------------------------------------


class WorkoutPlanCreate(RequestModel):
    """Request schema for creating a workout plan."""

    plan_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    goal: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )


class WorkoutPlanUpdate(PartialUpdateModel):
    """Request schema for updating a workout plan."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"plan_name", "goal"})

    plan_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    goal: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )


class WorkoutPlanResponse(BaseModel):
    """Response schema for a workout plan."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: int
    user_id: int
    plan_name: str
    goal: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Training prescription schemas (plan exercises)
# ---------------------------------------------------------------------------
#
# A training prescription is a structured set of exercise parameters that
# describes how an exercise is intended to be performed within a plan. It is
# training programming, not medical treatment.


class PlanExerciseCreate(RequestModel):
    """Request schema for prescribing an exercise within a plan session."""

    exercise_id: int = Field(
        ...,
        gt=0,
    )
    position: int = Field(
        default=0,
        ge=0,
        le=1000,
    )
    sets: int = Field(
        ...,
        gt=0,
        le=100,
    )
    reps_min: int = Field(
        ...,
        gt=0,
        le=1000,
    )
    reps_max: int = Field(
        ...,
        gt=0,
        le=1000,
        description="Upper end of the rep range; equal to reps_min for a fixed target.",
    )
    weight: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    rpe: Decimal | None = Field(
        default=None,
        ge=1,
        le=10,
        max_digits=3,
        decimal_places=1,
        description="Target rating of perceived exertion, 1-10.",
    )
    rir: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Target repetitions in reserve.",
    )
    rest_seconds: int | None = Field(
        default=None,
        ge=0,
        le=3600,
    )
    tempo: str | None = Field(
        default=None,
        pattern=r"^[0-9Xx-]{1,20}$",
        description="Tempo notation such as 3-1-1-0.",
    )
    duration_seconds: int | None = Field(
        default=None,
        gt=0,
        le=86_400,
    )
    distance_miles: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @model_validator(mode="after")
    def validate_rep_range(self) -> Self:
        if self.reps_max < self.reps_min:
            raise ValueError("reps_max must be greater than or equal to reps_min.")
        return self


class PlanExerciseUpdate(PartialUpdateModel):
    """Request schema for partially updating a prescribed exercise.

    When only one end of the rep range is sent, the endpoint checks it against
    the stored value of the other end.
    """

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"position", "sets", "reps_min", "reps_max"}
    )

    position: int | None = Field(default=None, ge=0, le=1000)
    sets: int | None = Field(default=None, gt=0, le=100)
    reps_min: int | None = Field(default=None, gt=0, le=1000)
    reps_max: int | None = Field(default=None, gt=0, le=1000)
    weight: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    rpe: Decimal | None = Field(
        default=None,
        ge=1,
        le=10,
        max_digits=3,
        decimal_places=1,
    )
    rir: int | None = Field(default=None, ge=0, le=10)
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    tempo: str | None = Field(default=None, pattern=r"^[0-9Xx-]{1,20}$")
    duration_seconds: int | None = Field(default=None, gt=0, le=86_400)
    distance_miles: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_rep_range(self) -> Self:
        if (
            self.reps_min is not None
            and self.reps_max is not None
            and self.reps_max < self.reps_min
        ):
            raise ValueError("reps_max must be greater than or equal to reps_min.")
        return self


class PlanExerciseResponse(BaseModel):
    """Response schema for a prescribed exercise."""

    model_config = ConfigDict(from_attributes=True)

    plan_exercise_id: int
    session_id: int
    exercise_id: int
    position: int
    sets: int
    reps_min: int
    reps_max: int
    weight: Decimal | None
    rpe: Decimal | None
    rir: int | None
    rest_seconds: int | None
    tempo: str | None
    duration_seconds: int | None
    distance_miles: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    exercise: ExerciseResponse


# ---------------------------------------------------------------------------
# Plan session schemas
# ---------------------------------------------------------------------------


class PlanSessionCreate(RequestModel):
    """Request schema for adding a session to a workout plan."""

    session_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    position: int = Field(
        default=0,
        ge=0,
        le=1000,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class PlanSessionUpdate(PartialUpdateModel):
    """Request schema for updating a plan session."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"session_name", "position"}
    )

    session_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    position: int | None = Field(
        default=None,
        ge=0,
        le=1000,
    )
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class PlanSessionResponse(BaseModel):
    """Response schema for a plan session without nested exercises."""

    model_config = ConfigDict(from_attributes=True)

    session_id: int
    plan_id: int
    session_name: str
    position: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PlanSessionDetailResponse(PlanSessionResponse):
    """Plan session including its prescribed exercises."""

    exercises: list[PlanExerciseResponse] = Field(
        default_factory=list,
    )


class WorkoutPlanDetailResponse(WorkoutPlanResponse):
    """Workout plan including its sessions and prescribed exercises."""

    sessions: list[PlanSessionDetailResponse] = Field(
        default_factory=list,
    )


# ---------------------------------------------------------------------------
# RAG schemas
# ---------------------------------------------------------------------------


class AskRequest(RequestModel):
    """Request schema for an AI fitness question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class SourceDocument(BaseModel):
    """Source document returned by the RAG pipeline."""

    document: str
    content: str | None = None
    distance: float | None = None


class AskResponse(BaseModel):
    """Response schema for an AI-generated fitness answer."""

    answer: str
    sources: list[SourceDocument] = Field(
        default_factory=list,
    )
    confidence: float | None = None
    chunks_retrieved: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Health/status schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response schema for the application health endpoint."""

    status: str
    database: str
    ollama: str | None = None
    chromadb: str | None = None

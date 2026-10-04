"""SQLAlchemy ORM models for the fitness tracking application."""

from datetime import date, datetime
from decimal import Decimal

from database import Base
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class TimestampMixin:
    """Audit timestamps for resources that can be edited after creation.

    Both values are maintained by the database clock so they are consistent
    regardless of which application instance performs the write.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(Base):
    """Application user who owns fitness data."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workouts: Mapped[list["Workout"]] = relationship(
        "Workout",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    workout_plans: Mapped[list["WorkoutPlan"]] = relationship(
        "WorkoutPlan",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    custom_exercises: Mapped[list["Exercise"]] = relationship(
        "Exercise",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, username={self.username!r})"


class Workout(TimestampMixin, Base):
    """A workout session completed by a user."""

    __tablename__ = "workouts"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0",
            name="ck_workouts_duration_minutes_positive",
        ),
        Index("ix_workouts_user_id_workout_date", "user_id", "workout_date"),
    )

    workout_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    workout_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="workouts",
    )

    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise",
        back_populates="workout",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutExercise.position",
    )

    def __repr__(self) -> str:
        return (
            f"Workout(workout_id={self.workout_id!r}, "
            f"user_id={self.user_id!r}, workout_date={self.workout_date!r})"
        )


class Exercise(TimestampMixin, Base):
    """Exercise definition that can be used in multiple workouts.

    Two kinds of exercises exist:

    - System exercises (``user_id IS NULL``): the shared library, readable by
      everyone and not modifiable through the user-facing API.
    - Custom exercises (``user_id`` set): created by, visible to, and
      modifiable only by their owner.

    Deleting an exercise that is referenced by any workout is blocked at the
    database level.
    """

    __tablename__ = "exercises"
    __table_args__ = (
        # One custom exercise name per user.
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_exercises_user_id_name",
        ),
        # NULLs are distinct in a plain unique constraint, so system exercise
        # names need their own partial unique index.
        Index(
            "uq_exercises_system_name",
            "name",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
            sqlite_where=text("user_id IS NULL"),
        ),
    )

    exercise_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    muscle_group: Mapped[str] = mapped_column(String(100), nullable=False)
    equipment: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped["User | None"] = relationship(
        "User",
        back_populates="custom_exercises",
    )

    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise",
        back_populates="exercise",
        passive_deletes=True,
    )

    plan_exercises: Mapped[list["PlanExercise"]] = relationship(
        "PlanExercise",
        back_populates="exercise",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Exercise(exercise_id={self.exercise_id!r}, name={self.name!r})"


class WorkoutExercise(Base):
    """A single exercise entry within a workout.

    Every workout exercise requires at least one set and one rep. This
    requirement applies to both strength and time/distance-based exercises.

    Additional performance measurements are optional:

    - ``weight`` records resistance used for strength exercises.
    - ``duration_seconds`` records time-based performance.
    - ``distance_miles`` records distance-based performance.

    Duration and distance may be recorded together, which supports activities
    such as running and cycling. Time- or distance-based activities can use
    ``sets=1`` and ``reps=1`` to represent one continuous effort while their
    actual performance is recorded with duration and/or distance.

    The same structure supports strength, timed, distance-based, and combined
    exercises without requiring separate tables.
    """

    __tablename__ = "workout_exercises"
    __table_args__ = (
        CheckConstraint("sets > 0", name="ck_workout_exercises_sets_positive"),
        CheckConstraint("reps > 0", name="ck_workout_exercises_reps_positive"),
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_workout_exercises_weight_non_negative",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_workout_exercises_duration_seconds_positive",
        ),
        CheckConstraint(
            "distance_miles IS NULL OR distance_miles >= 0",
            name="ck_workout_exercises_distance_miles_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_workout_exercises_position_non_negative",
        ),
        Index("ix_workout_exercises_workout_id_position", "workout_id", "position"),
    )

    workout_exercise_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.workout_id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.exercise_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    distance_miles: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    workout: Mapped["Workout"] = relationship(
        "Workout",
        back_populates="workout_exercises",
    )

    exercise: Mapped["Exercise"] = relationship(
        "Exercise",
        back_populates="workout_exercises",
    )

    def __repr__(self) -> str:
        return (
            f"WorkoutExercise(workout_exercise_id={self.workout_exercise_id!r}, "
            f"workout_id={self.workout_id!r}, exercise_id={self.exercise_id!r})"
        )


class WorkoutPlan(TimestampMixin, Base):
    """Training plan owned by a user.

    A plan states a goal and contains an ordered list of sessions (for
    example "Push", "Pull", "Legs"). Each session holds the exercise
    prescriptions that describe how the user intends to train.
    """

    __tablename__ = "workout_plans"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "plan_name",
            name="uq_workout_plans_user_id_plan_name",
        ),
    )

    plan_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="workout_plans",
    )

    sessions: Mapped[list["PlanSession"]] = relationship(
        "PlanSession",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanSession.position",
    )

    def __repr__(self) -> str:
        return f"WorkoutPlan(plan_id={self.plan_id!r}, plan_name={self.plan_name!r})"


class PlanSession(TimestampMixin, Base):
    """One planned training session within a workout plan (e.g. "Full Body A")."""

    __tablename__ = "plan_sessions"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_plan_sessions_position_non_negative",
        ),
        Index("ix_plan_sessions_plan_id_position", "plan_id", "position"),
    )

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("workout_plans.plan_id", ondelete="CASCADE"),
        nullable=False,
    )
    session_name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["WorkoutPlan"] = relationship(
        "WorkoutPlan",
        back_populates="sessions",
    )

    exercises: Mapped[list["PlanExercise"]] = relationship(
        "PlanExercise",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanExercise.position",
    )

    def __repr__(self) -> str:
        return (
            f"PlanSession(session_id={self.session_id!r}, "
            f"plan_id={self.plan_id!r}, session_name={self.session_name!r})"
        )


class PlanExercise(TimestampMixin, Base):
    """A training prescription: how one exercise is meant to be performed.

    A training prescription is a structured set of exercise parameters
    (sets, rep range, load, effort, rest, tempo) within a training plan. It
    describes intended training, not medical treatment.

    This is the planned counterpart of ``WorkoutExercise``, which records
    what the user actually did. Like ``WorkoutExercise``, every prescription
    requires sets and reps; time-based and distance-based work uses
    ``sets=1``, ``reps_min=1``, ``reps_max=1`` with ``duration_seconds``
    and/or ``distance_miles``.

    Fixed rep targets set ``reps_min`` equal to ``reps_max``.
    """

    __tablename__ = "plan_exercises"
    __table_args__ = (
        CheckConstraint("sets > 0", name="ck_plan_exercises_sets_positive"),
        CheckConstraint(
            "reps_min > 0",
            name="ck_plan_exercises_reps_min_positive",
        ),
        CheckConstraint(
            "reps_max >= reps_min",
            name="ck_plan_exercises_reps_max_gte_reps_min",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_plan_exercises_weight_non_negative",
        ),
        CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)",
            name="ck_plan_exercises_rpe_range",
        ),
        CheckConstraint(
            "rir IS NULL OR (rir >= 0 AND rir <= 10)",
            name="ck_plan_exercises_rir_range",
        ),
        CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0",
            name="ck_plan_exercises_rest_seconds_non_negative",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_plan_exercises_duration_seconds_positive",
        ),
        CheckConstraint(
            "distance_miles IS NULL OR distance_miles >= 0",
            name="ck_plan_exercises_distance_miles_non_negative",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_plan_exercises_position_non_negative",
        ),
        Index("ix_plan_exercises_session_id_position", "session_id", "position"),
    )

    plan_exercise_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("plan_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.exercise_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Required for every prescription.
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_min: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_max: Mapped[int] = mapped_column(Integer, nullable=False)

    # Optional targets.
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    rir: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tempo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_miles: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["PlanSession"] = relationship(
        "PlanSession",
        back_populates="exercises",
    )

    exercise: Mapped["Exercise"] = relationship(
        "Exercise",
        back_populates="plan_exercises",
    )

    def __repr__(self) -> str:
        return (
            f"PlanExercise(plan_exercise_id={self.plan_exercise_id!r}, "
            f"session_id={self.session_id!r}, exercise_id={self.exercise_id!r})"
        )

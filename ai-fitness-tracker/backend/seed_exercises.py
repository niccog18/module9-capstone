"""Load the shared system exercise library (exercises with no owner).

Usage (from the backend directory / inside the backend container):

    python seed_exercises.py

Safe to run repeatedly: exercises whose name already exists in the system
library are skipped, so nothing is duplicated and nothing is overwritten.
Start the backend once first so the database tables exist.
"""

from models import Exercise
from sqlalchemy import select
from sqlalchemy.orm import Session

# (name, muscle_group, equipment, description)
SYSTEM_EXERCISES: list[tuple[str, str, str, str]] = [
    # Chest
    (
        "Barbell Bench Press",
        "chest",
        "barbell",
        "Press a barbell from the chest while lying on a flat bench.",
    ),
    (
        "Incline Dumbbell Press",
        "chest",
        "dumbbell",
        "Press dumbbells upward from an inclined bench to train the upper chest.",
    ),
    (
        "Dumbbell Fly",
        "chest",
        "dumbbell",
        "Open and close the arms in an arc with dumbbells to stretch and contract the chest.",
    ),
    (
        "Push-Up",
        "chest",
        "bodyweight",
        "Lower and press the body from the floor with the hands under the shoulders.",
    ),
    (
        "Cable Crossover",
        "chest",
        "cable",
        "Bring the handles of two high cables together in front of the chest.",
    ),
    # Back
    (
        "Deadlift",
        "back",
        "barbell",
        "Lift a barbell from the floor to hip height by extending the hips and knees.",
    ),
    (
        "Barbell Row",
        "back",
        "barbell",
        "Pull a barbell toward the lower ribs from a hip-hinged position.",
    ),
    (
        "Pull-Up",
        "back",
        "bodyweight",
        "Pull the body up to a bar with an overhand grip.",
    ),
    (
        "Chin-Up",
        "back",
        "bodyweight",
        "Pull the body up to a bar with an underhand grip.",
    ),
    (
        "Lat Pulldown",
        "back",
        "cable",
        "Pull a bar down to the upper chest from a seated position.",
    ),
    (
        "Seated Cable Row",
        "back",
        "cable",
        "Pull a cable handle toward the torso while seated with the chest up.",
    ),
    (
        "One-Arm Dumbbell Row",
        "back",
        "dumbbell",
        "Row a dumbbell toward the hip with one hand supported on a bench.",
    ),
    # Shoulders
    (
        "Overhead Press",
        "shoulders",
        "barbell",
        "Press a barbell from the shoulders to overhead while standing.",
    ),
    (
        "Dumbbell Shoulder Press",
        "shoulders",
        "dumbbell",
        "Press dumbbells from shoulder height to overhead.",
    ),
    (
        "Dumbbell Lateral Raise",
        "shoulders",
        "dumbbell",
        "Raise dumbbells out to the sides to shoulder height.",
    ),
    (
        "Face Pull",
        "shoulders",
        "cable",
        "Pull a rope attachment toward the face to train the rear shoulders and upper back.",
    ),
    (
        "Rear Delt Fly",
        "shoulders",
        "dumbbell",
        "Raise dumbbells out to the sides while bent forward to train the rear shoulders.",
    ),
    # Arms
    (
        "Barbell Curl",
        "biceps",
        "barbell",
        "Curl a barbell from the thighs to the shoulders.",
    ),
    (
        "Hammer Curl",
        "biceps",
        "dumbbell",
        "Curl dumbbells with the palms facing each other.",
    ),
    (
        "Triceps Pushdown",
        "triceps",
        "cable",
        "Press a cable attachment down by extending the elbows.",
    ),
    (
        "Skull Crusher",
        "triceps",
        "barbell",
        "Lower a barbell toward the forehead by bending the elbows, then extend.",
    ),
    (
        "Overhead Triceps Extension",
        "triceps",
        "dumbbell",
        "Extend the elbows to press a dumbbell overhead from behind the head.",
    ),
    (
        "Bench Dip",
        "triceps",
        "bodyweight",
        "Lower and press the body between two benches using the arms.",
    ),
    # Legs
    (
        "Back Squat",
        "quadriceps",
        "barbell",
        "Squat with a barbell on the upper back, then stand up.",
    ),
    (
        "Front Squat",
        "quadriceps",
        "barbell",
        "Squat with a barbell held across the front of the shoulders.",
    ),
    (
        "Goblet Squat",
        "quadriceps",
        "dumbbell",
        "Squat while holding a single dumbbell or kettlebell at the chest.",
    ),
    (
        "Leg Press",
        "quadriceps",
        "machine",
        "Press a weighted platform away with the legs while seated.",
    ),
    (
        "Leg Extension",
        "quadriceps",
        "machine",
        "Extend the knees against resistance while seated.",
    ),
    (
        "Bulgarian Split Squat",
        "quadriceps",
        "dumbbell",
        "Squat on one leg with the rear foot elevated on a bench.",
    ),
    (
        "Walking Lunge",
        "quadriceps",
        "dumbbell",
        "Step forward into a lunge and alternate legs while moving forward.",
    ),
    (
        "Romanian Deadlift",
        "hamstrings",
        "barbell",
        "Lower a barbell along the legs by hinging at the hips, then stand.",
    ),
    (
        "Leg Curl",
        "hamstrings",
        "machine",
        "Curl the heels toward the glutes against resistance.",
    ),
    (
        "Hip Thrust",
        "glutes",
        "barbell",
        "Drive the hips upward with the upper back supported on a bench.",
    ),
    (
        "Glute Bridge",
        "glutes",
        "bodyweight",
        "Lie on the back and lift the hips by squeezing the glutes.",
    ),
    (
        "Kettlebell Swing",
        "glutes",
        "kettlebell",
        "Swing a kettlebell from between the legs to chest height with a hip hinge.",
    ),
    (
        "Standing Calf Raise",
        "calves",
        "machine",
        "Rise onto the toes against resistance while standing.",
    ),
    (
        "Seated Calf Raise",
        "calves",
        "machine",
        "Rise onto the toes against resistance while seated.",
    ),
    # Core
    (
        "Plank",
        "core",
        "bodyweight",
        "Hold a straight-body position on the forearms and toes.",
    ),
    (
        "Hanging Leg Raise",
        "core",
        "bodyweight",
        "Raise the legs while hanging from a bar.",
    ),
    (
        "Cable Crunch",
        "core",
        "cable",
        "Crunch the torso downward against a cable while kneeling.",
    ),
    (
        "Ab Wheel Rollout",
        "core",
        "ab wheel",
        "Roll an ab wheel forward from the knees and pull it back.",
    ),
    # Cardio (log time and distance; use 1 set of 1 rep)
    ("Running", "cardio", "none", "Continuous running, outdoors or on a treadmill."),
    (
        "Cycling",
        "cardio",
        "bicycle",
        "Continuous cycling, outdoors or on a stationary bike.",
    ),
    (
        "Rowing Machine",
        "cardio",
        "rowing machine",
        "Continuous rowing on an indoor rowing machine.",
    ),
    ("Swimming", "cardio", "pool", "Continuous swimming laps."),
    ("Walking", "cardio", "none", "Continuous brisk walking."),
    ("Jump Rope", "cardio", "jump rope", "Continuous skipping with a rope."),
]


def seed_system_exercises(db: Session) -> tuple[int, int]:
    """Insert missing system exercises. Return (added, already_present)."""

    existing_names = set(
        db.scalars(select(Exercise.name).where(Exercise.user_id.is_(None)))
    )

    added = 0
    for name, muscle_group, equipment, description in SYSTEM_EXERCISES:
        if name in existing_names:
            continue
        db.add(
            Exercise(
                user_id=None,
                name=name,
                muscle_group=muscle_group,
                equipment=equipment,
                description=description,
            )
        )
        added += 1

    db.commit()
    return added, len(SYSTEM_EXERCISES) - added


def main() -> int:
    # Imported here so importing this module (for example in tests) does not
    # require DATABASE_URL.
    from database import Base, SessionLocal, engine

    # Idempotent: makes the seed safe to run before the API has ever started
    # (for example from the container's startup command on a fresh database).
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        added, present = seed_system_exercises(db)

    print(f"Done: {added} added, {present} already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

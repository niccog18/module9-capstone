"""Tests for the system exercise seed script."""

from models import Exercise
from seed_exercises import SYSTEM_EXERCISES, seed_system_exercises
from sqlalchemy import func, select


def count_system_exercises(db):
    return db.scalar(
        select(func.count()).select_from(Exercise).where(Exercise.user_id.is_(None))
    )


def test_seed_data_is_valid():
    names = [name for name, *_ in SYSTEM_EXERCISES]

    assert len(names) == len(set(names)), "duplicate exercise names"
    for name, muscle_group, equipment, description in SYSTEM_EXERCISES:
        assert 0 < len(name) <= 100
        assert 0 < len(muscle_group) <= 100
        assert 0 < len(equipment) <= 100
        assert description


def test_seed_adds_system_exercises_once(session_factory):
    with session_factory() as db:
        first = seed_system_exercises(db)
        second = seed_system_exercises(db)
        total = count_system_exercises(db)

    assert first == (len(SYSTEM_EXERCISES), 0)
    assert second == (0, len(SYSTEM_EXERCISES))
    assert total == len(SYSTEM_EXERCISES)


def test_seeded_exercises_are_visible_but_read_only(
    client, auth_headers, session_factory
):
    with session_factory() as db:
        seed_system_exercises(db)

    listed = client.get("/api/v1/exercises?limit=500", headers=auth_headers).json()
    squat = next(item for item in listed if item["name"] == "Back Squat")

    assert len(listed) == len(SYSTEM_EXERCISES)
    assert squat["user_id"] is None
    patch = client.patch(
        f"/api/v1/exercises/{squat['exercise_id']}",
        json={"name": "Changed"},
        headers=auth_headers,
    )
    assert patch.status_code == 403

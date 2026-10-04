"""Capstone backend tests for workouts and the exercises performed in them."""

import pytest
from models import Exercise

WORKOUTS = "/api/v1/workouts"
EXERCISES = "/api/v1/exercises"

WORKOUT = {
    "workout_date": "2026-10-01",
    "duration_minutes": 45,
    "notes": "Upper body",
}


def create_workout(client, headers, **overrides):
    return client.post(WORKOUTS, json={**WORKOUT, **overrides}, headers=headers)


def create_exercise(client, headers, name="Pytest Bench Press"):
    response = client.post(
        EXERCISES,
        json={"name": name, "muscle_group": "chest", "equipment": "barbell"},
        headers=headers,
    )
    return response.json()["exercise_id"]


def add_exercise(client, headers, workout_id, exercise_id, **overrides):
    body = {"exercise_id": exercise_id, "position": 0, "sets": 3, "reps": 10}
    return client.post(
        f"{WORKOUTS}/{workout_id}/exercises",
        json={**body, **overrides},
        headers=headers,
    )


# --- Workout CRUD -----------------------------------------------------------


def test_workouts_require_auth(client):
    assert client.get(WORKOUTS).status_code == 401


def test_create_workout(client, auth_headers):
    response = create_workout(client, auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["workout_date"] == "2026-10-01"
    assert data["duration_minutes"] == 45
    assert data["notes"] == "Upper body"
    assert data["workout_id"] > 0


def test_list_returns_only_your_workouts(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")
    create_workout(client, alice)
    create_workout(client, alice, notes="Legs")
    create_workout(client, bob)

    alice_list = client.get(WORKOUTS, headers=alice).json()
    bob_list = client.get(WORKOUTS, headers=bob).json()

    assert len(alice_list) == 2
    assert len(bob_list) == 1
    assert {w["workout_id"] for w in alice_list}.isdisjoint(
        {w["workout_id"] for w in bob_list}
    )


def test_get_workout_detail_includes_exercises(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)
    add_exercise(client, auth_headers, workout_id, exercise_id)

    response = client.get(f"{WORKOUTS}/{workout_id}", headers=auth_headers)

    assert response.status_code == 200
    exercises = response.json()["exercises"]
    assert len(exercises) == 1
    assert exercises[0]["sets"] == 3
    assert exercises[0]["exercise"]["name"] == "Pytest Bench Press"


def test_patch_workout_changes_only_sent_fields(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]

    response = client.patch(
        f"{WORKOUTS}/{workout_id}",
        json={"duration_minutes": 60},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["duration_minutes"] == 60
    assert data["notes"] == "Upper body"
    assert data["workout_date"] == "2026-10-01"


def test_patch_can_clear_nullable_notes(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]

    response = client.patch(
        f"{WORKOUTS}/{workout_id}", json={"notes": None}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["notes"] is None


def test_delete_workout_removes_it_and_its_entries(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)
    add_exercise(client, auth_headers, workout_id, exercise_id)

    assert (
        client.delete(f"{WORKOUTS}/{workout_id}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.get(f"{WORKOUTS}/{workout_id}", headers=auth_headers).status_code == 404
    )
    # The exercise itself is not deleted with the workout.
    assert (
        client.get(f"{EXERCISES}/{exercise_id}", headers=auth_headers).status_code
        == 200
    )


# --- Ownership --------------------------------------------------------------


def test_other_users_workout_is_hidden(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")
    workout_id = create_workout(client, alice).json()["workout_id"]
    exercise_id = create_exercise(client, bob)
    url = f"{WORKOUTS}/{workout_id}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"notes": "x"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.get(f"{url}/exercises", headers=bob).status_code == 404
    assert add_exercise(client, bob, workout_id, exercise_id).status_code == 404

    # Alice's workout is untouched.
    assert client.get(url, headers=alice).json()["notes"] == "Upper body"


# --- Validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"duration_minutes": 0},
        {"duration_minutes": -5},
        {"duration_minutes": 1441},
        {"workout_date": "not-a-date"},
    ],
)
def test_create_workout_validates_input(client, auth_headers, overrides):
    assert create_workout(client, auth_headers, **overrides).status_code == 422


def test_create_workout_rejects_unknown_fields(client, auth_headers):
    response = create_workout(client, auth_headers, favourite_colour="blue")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [{}, {"duration_minutes": None}, {"workout_date": None}],
)
def test_patch_workout_validates_input(client, auth_headers, body):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]

    response = client.patch(f"{WORKOUTS}/{workout_id}", json=body, headers=auth_headers)

    assert response.status_code == 422


# --- Exercises within a workout ---------------------------------------------


def test_add_exercise_with_sets_reps_and_weight(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = add_exercise(
        client, auth_headers, workout_id, exercise_id, sets=4, reps=6, weight=135.5
    )

    assert response.status_code == 201
    data = response.json()
    assert data["sets"] == 4
    assert data["reps"] == 6
    assert float(data["weight"]) == 135.5
    assert data["exercise"]["exercise_id"] == exercise_id


def test_cardio_entry_records_duration_and_distance(client, auth_headers):
    """A bike ride is 1 set of 1 rep with its time and distance recorded."""

    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers, name="Pytest Cycling")

    response = add_exercise(
        client,
        auth_headers,
        workout_id,
        exercise_id,
        sets=1,
        reps=1,
        duration_seconds=2700,
        distance_miles=12.5,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["duration_seconds"] == 2700
    assert float(data["distance_miles"]) == 12.5


def test_same_exercise_can_appear_twice_in_a_workout(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)

    first = add_exercise(client, auth_headers, workout_id, exercise_id, position=0)
    second = add_exercise(client, auth_headers, workout_id, exercise_id, position=1)

    assert first.status_code == second.status_code == 201
    assert first.json()["workout_exercise_id"] != second.json()["workout_exercise_id"]
    entries = client.get(f"{WORKOUTS}/{workout_id}/exercises", headers=auth_headers)
    assert len(entries.json()) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"sets": 0},
        {"reps": 0},
        {"weight": -1},
        {"duration_seconds": 0},
        {"distance_miles": -0.5},
        {"position": -1},
    ],
)
def test_add_exercise_validates_input(client, auth_headers, overrides):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = add_exercise(client, auth_headers, workout_id, exercise_id, **overrides)

    assert response.status_code == 422


def test_sets_and_reps_are_required(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = client.post(
        f"{WORKOUTS}/{workout_id}/exercises",
        json={"exercise_id": exercise_id},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_update_workout_exercise(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)
    entry_id = add_exercise(client, auth_headers, workout_id, exercise_id).json()[
        "workout_exercise_id"
    ]
    url = f"{WORKOUTS}/{workout_id}/exercises/{entry_id}"

    updated = client.patch(url, json={"sets": 5, "weight": 100}, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["sets"] == 5
    assert updated.json()["reps"] == 10

    null_sets = client.patch(url, json={"sets": None}, headers=auth_headers)
    assert null_sets.status_code == 422


def test_delete_workout_exercise(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)
    entry_id = add_exercise(client, auth_headers, workout_id, exercise_id).json()[
        "workout_exercise_id"
    ]
    url = f"{WORKOUTS}/{workout_id}/exercises/{entry_id}"

    assert client.delete(url, headers=auth_headers).status_code == 204
    entries = client.get(f"{WORKOUTS}/{workout_id}/exercises", headers=auth_headers)
    assert entries.json() == []


def test_cannot_use_another_users_custom_exercise(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")
    alice_exercise = create_exercise(client, alice)
    bob_workout = create_workout(client, bob).json()["workout_id"]

    response = add_exercise(client, bob, bob_workout, alice_exercise)

    assert response.status_code == 404


def test_can_use_a_system_exercise(client, auth_headers, session_factory):
    with session_factory() as db:
        system_exercise = Exercise(
            user_id=None, name="System Row", muscle_group="back", equipment="cable"
        )
        db.add(system_exercise)
        db.commit()
        system_id = system_exercise.exercise_id
    workout_id = create_workout(client, auth_headers).json()["workout_id"]

    response = add_exercise(client, auth_headers, workout_id, system_id)

    assert response.status_code == 201


def test_exercise_used_in_a_workout_cannot_be_deleted(client, auth_headers):
    workout_id = create_workout(client, auth_headers).json()["workout_id"]
    exercise_id = create_exercise(client, auth_headers)
    add_exercise(client, auth_headers, workout_id, exercise_id)

    response = client.delete(f"{EXERCISES}/{exercise_id}", headers=auth_headers)

    assert response.status_code == 409

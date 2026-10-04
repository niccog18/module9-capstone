"""Capstone backend tests for the core CRUD resource: exercises."""

from models import Exercise

BASE = "/api/v1/exercises"

SQUAT = {
    "name": "Pytest Squat",
    "muscle_group": "legs",
    "equipment": "barbell",
    "description": "Back squat.",
}


def create_exercise(client, headers, **overrides):
    return client.post(BASE, json={**SQUAT, **overrides}, headers=headers)


def test_create_exercise(client, auth_headers):
    """Creating an exercise returns 201 and a user-owned record."""

    response = create_exercise(client, auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == SQUAT["name"]
    assert data["muscle_group"] == SQUAT["muscle_group"]
    assert data["user_id"] is not None
    assert data["exercise_id"] > 0


def test_list_and_get_exercise(client, auth_headers):
    """A created exercise appears in the list and can be fetched by id."""

    exercise_id = create_exercise(client, auth_headers).json()["exercise_id"]

    listed = client.get(BASE, headers=auth_headers)
    assert listed.status_code == 200
    assert exercise_id in [item["exercise_id"] for item in listed.json()]

    fetched = client.get(f"{BASE}/{exercise_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == SQUAT["name"]


def test_patch_updates_only_sent_fields(client, auth_headers):
    """PATCH changes the fields in the body and leaves the others alone."""

    exercise_id = create_exercise(client, auth_headers).json()["exercise_id"]

    response = client.patch(
        f"{BASE}/{exercise_id}",
        json={"equipment": "smith machine"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["equipment"] == "smith machine"
    assert data["name"] == SQUAT["name"]
    assert data["description"] == SQUAT["description"]


def test_delete_exercise(client, auth_headers):
    """Deleting an exercise returns 204 and it can no longer be fetched."""

    exercise_id = create_exercise(client, auth_headers).json()["exercise_id"]

    deleted = client.delete(f"{BASE}/{exercise_id}", headers=auth_headers)
    assert deleted.status_code == 204

    fetched = client.get(f"{BASE}/{exercise_id}", headers=auth_headers)
    assert fetched.status_code == 404


def test_duplicate_exercise_name_conflicts(client, auth_headers):
    """A user cannot create two custom exercises with the same name."""

    assert create_exercise(client, auth_headers).status_code == 201

    response = create_exercise(client, auth_headers)

    assert response.status_code == 409


def test_other_users_exercise_is_hidden(client, make_auth_headers):
    """Another user's custom exercise is reported as 404, not 403."""

    owner = make_auth_headers("owner_user")
    other = make_auth_headers("other_user")
    exercise_id = create_exercise(client, owner).json()["exercise_id"]

    assert client.get(f"{BASE}/{exercise_id}", headers=other).status_code == 404
    assert (
        client.patch(
            f"{BASE}/{exercise_id}", json={"name": "Hijacked"}, headers=other
        ).status_code
        == 404
    )
    assert client.delete(f"{BASE}/{exercise_id}", headers=other).status_code == 404


def test_system_exercise_is_read_only(client, auth_headers, session_factory):
    """System exercises are visible to users but cannot be modified."""

    with session_factory() as db:
        system_exercise = Exercise(
            user_id=None,
            name="System Plank",
            muscle_group="core",
            equipment="none",
        )
        db.add(system_exercise)
        db.commit()
        system_id = system_exercise.exercise_id

    assert client.get(f"{BASE}/{system_id}", headers=auth_headers).status_code == 200
    assert (
        client.patch(
            f"{BASE}/{system_id}", json={"name": "Changed"}, headers=auth_headers
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/{system_id}", headers=auth_headers).status_code == 403
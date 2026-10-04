"""Capstone backend tests for plans, sessions and training prescriptions."""

import pytest
from models import Exercise

PLANS = "/api/v1/plans"
EXERCISES = "/api/v1/exercises"

PLAN = {"plan_name": "Push Pull Legs", "goal": "Build muscle"}


def create_plan(client, headers, **overrides):
    return client.post(PLANS, json={**PLAN, **overrides}, headers=headers)


def create_session(client, headers, plan_id, **overrides):
    body = {"session_name": "Push Day", "position": 0}
    return client.post(
        f"{PLANS}/{plan_id}/sessions", json={**body, **overrides}, headers=headers
    )


def create_exercise(client, headers, name="Pytest Bench Press"):
    response = client.post(
        EXERCISES,
        json={"name": name, "muscle_group": "chest", "equipment": "barbell"},
        headers=headers,
    )
    return response.json()["exercise_id"]


def prescribe(client, headers, plan_id, session_id, exercise_id, **overrides):
    body = {"exercise_id": exercise_id, "sets": 3, "reps_min": 6, "reps_max": 8}
    return client.post(
        f"{PLANS}/{plan_id}/sessions/{session_id}/exercises",
        json={**body, **overrides},
        headers=headers,
    )


@pytest.fixture()
def built_plan(client, auth_headers):
    """A plan with one session and one prescribed exercise."""

    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_id).json()["session_id"]
    exercise_id = create_exercise(client, auth_headers)
    prescription = prescribe(client, auth_headers, plan_id, session_id, exercise_id)
    return {
        "plan_id": plan_id,
        "session_id": session_id,
        "exercise_id": exercise_id,
        "plan_exercise_id": prescription.json()["plan_exercise_id"],
    }


# --- Plans ------------------------------------------------------------------


def test_plans_require_auth(client):
    assert client.get(PLANS).status_code == 401


def test_create_and_list_plans(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")

    created = create_plan(client, alice)
    create_plan(client, bob, plan_name="Bob's plan")

    assert created.status_code == 201
    assert created.json()["plan_name"] == "Push Pull Legs"
    listed = client.get(PLANS, headers=alice).json()
    assert [plan["plan_name"] for plan in listed] == ["Push Pull Legs"]


def test_plan_detail_nests_sessions_and_prescriptions(client, auth_headers, built_plan):
    response = client.get(f"{PLANS}/{built_plan['plan_id']}", headers=auth_headers)

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_name"] == "Push Day"
    prescriptions = sessions[0]["exercises"]
    assert len(prescriptions) == 1
    assert prescriptions[0]["reps_min"] == 6
    assert prescriptions[0]["exercise"]["name"] == "Pytest Bench Press"


def test_patch_plan_changes_only_sent_fields(client, auth_headers):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]

    response = client.patch(
        f"{PLANS}/{plan_id}", json={"goal": "Get stronger"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["goal"] == "Get stronger"
    assert response.json()["plan_name"] == "Push Pull Legs"


@pytest.mark.parametrize(
    "body",
    [{}, {"plan_name": None}, {"goal": None}, {"plan_name": ""}],
)
def test_patch_plan_validates_input(client, auth_headers, body):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]

    response = client.patch(f"{PLANS}/{plan_id}", json=body, headers=auth_headers)

    assert response.status_code == 422


def test_delete_plan_removes_its_sessions_but_keeps_exercises(
    client, auth_headers, built_plan
):
    url = f"{PLANS}/{built_plan['plan_id']}"

    assert client.delete(url, headers=auth_headers).status_code == 204
    assert client.get(url, headers=auth_headers).status_code == 404
    exercise = client.get(
        f"{EXERCISES}/{built_plan['exercise_id']}", headers=auth_headers
    )
    assert exercise.status_code == 200


# --- Sessions ---------------------------------------------------------------


def test_session_crud(client, auth_headers):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    created = create_session(client, auth_headers, plan_id, notes="Chest focus")
    session_id = created.json()["session_id"]
    url = f"{PLANS}/{plan_id}/sessions/{session_id}"

    assert created.status_code == 201
    assert (
        len(client.get(f"{PLANS}/{plan_id}/sessions", headers=auth_headers).json()) == 1
    )
    assert client.get(url, headers=auth_headers).json()["exercises"] == []

    patched = client.patch(url, json={"session_name": "Pull Day"}, headers=auth_headers)
    assert patched.json()["session_name"] == "Pull Day"
    assert patched.json()["notes"] == "Chest focus"

    assert client.delete(url, headers=auth_headers).status_code == 204
    assert client.get(url, headers=auth_headers).status_code == 404


def test_session_must_belong_to_the_plan_in_the_url(client, auth_headers):
    plan_one = create_plan(client, auth_headers).json()["plan_id"]
    plan_two = create_plan(client, auth_headers, plan_name="Second").json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_one).json()["session_id"]

    response = client.get(
        f"{PLANS}/{plan_two}/sessions/{session_id}", headers=auth_headers
    )

    assert response.status_code == 404


# --- Prescriptions ----------------------------------------------------------


def test_prescribe_an_exercise_with_all_parameters(client, auth_headers):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_id).json()["session_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = prescribe(
        client,
        auth_headers,
        plan_id,
        session_id,
        exercise_id,
        weight=135,
        rpe=7,
        rir=3,
        rest_seconds=180,
        tempo="3-1-1-0",
        notes="Pause on the chest",
    )

    assert response.status_code == 201
    data = response.json()
    assert (data["sets"], data["reps_min"], data["reps_max"]) == (3, 6, 8)
    assert float(data["rpe"]) == 7
    assert data["rir"] == 3
    assert data["rest_seconds"] == 180
    assert data["tempo"] == "3-1-1-0"
    assert data["exercise"]["exercise_id"] == exercise_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"reps_min": 8, "reps_max": 6},
        {"sets": 0},
        {"rpe": 11},
        {"rpe": 0.5},
        {"rir": 11},
        {"rest_seconds": -1},
        {"tempo": "slow"},
    ],
)
def test_prescription_validates_input(client, auth_headers, overrides):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_id).json()["session_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = prescribe(
        client, auth_headers, plan_id, session_id, exercise_id, **overrides
    )

    assert response.status_code == 422


def test_fixed_rep_target_allows_equal_min_and_max(client, auth_headers):
    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_id).json()["session_id"]
    exercise_id = create_exercise(client, auth_headers)

    response = prescribe(
        client, auth_headers, plan_id, session_id, exercise_id, reps_min=5, reps_max=5
    )

    assert response.status_code == 201


def test_update_prescription_checks_the_resulting_rep_range(
    client, auth_headers, built_plan
):
    url = (
        f"{PLANS}/{built_plan['plan_id']}/sessions/{built_plan['session_id']}"
        f"/exercises/{built_plan['plan_exercise_id']}"
    )

    valid = client.patch(url, json={"reps_max": 10, "rpe": 8}, headers=auth_headers)
    assert valid.status_code == 200
    assert valid.json()["reps_max"] == 10
    assert valid.json()["reps_min"] == 6

    # The stored reps_min is 6, so a lone reps_max of 5 would break the range.
    invalid = client.patch(url, json={"reps_max": 5}, headers=auth_headers)
    assert invalid.status_code == 422
    unchanged = client.get(
        f"{PLANS}/{built_plan['plan_id']}/sessions/{built_plan['session_id']}/exercises",
        headers=auth_headers,
    )
    assert unchanged.json()[0]["reps_max"] == 10


def test_delete_prescription(client, auth_headers, built_plan):
    base = (
        f"{PLANS}/{built_plan['plan_id']}/sessions/{built_plan['session_id']}/exercises"
    )

    deleted = client.delete(
        f"{base}/{built_plan['plan_exercise_id']}", headers=auth_headers
    )

    assert deleted.status_code == 204
    assert client.get(base, headers=auth_headers).json() == []


def test_prescription_can_use_a_system_exercise(client, auth_headers, session_factory):
    with session_factory() as db:
        system_exercise = Exercise(
            user_id=None, name="System Squat", muscle_group="legs", equipment="barbell"
        )
        db.add(system_exercise)
        db.commit()
        system_id = system_exercise.exercise_id
    plan_id = create_plan(client, auth_headers).json()["plan_id"]
    session_id = create_session(client, auth_headers, plan_id).json()["session_id"]

    response = prescribe(client, auth_headers, plan_id, session_id, system_id)

    assert response.status_code == 201


def test_cannot_prescribe_another_users_custom_exercise(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")
    alice_exercise = create_exercise(client, alice)
    plan_id = create_plan(client, bob).json()["plan_id"]
    session_id = create_session(client, bob, plan_id).json()["session_id"]

    response = prescribe(client, bob, plan_id, session_id, alice_exercise)

    assert response.status_code == 404


def test_exercise_used_in_a_plan_cannot_be_deleted(client, auth_headers, built_plan):
    response = client.delete(
        f"{EXERCISES}/{built_plan['exercise_id']}", headers=auth_headers
    )

    assert response.status_code == 409


# --- Ownership --------------------------------------------------------------


def test_other_users_plan_is_hidden_at_every_level(client, make_auth_headers):
    alice = make_auth_headers("alice")
    bob = make_auth_headers("bob")
    plan_id = create_plan(client, alice).json()["plan_id"]
    session_id = create_session(client, alice, plan_id).json()["session_id"]
    exercise_id = create_exercise(client, alice)
    plan_exercise_id = prescribe(
        client, alice, plan_id, session_id, exercise_id
    ).json()["plan_exercise_id"]

    plan_url = f"{PLANS}/{plan_id}"
    session_url = f"{plan_url}/sessions/{session_id}"
    prescription_url = f"{session_url}/exercises/{plan_exercise_id}"
    bob_exercise = create_exercise(client, bob)

    assert client.get(plan_url, headers=bob).status_code == 404
    assert client.patch(plan_url, json={"goal": "x"}, headers=bob).status_code == 404
    assert client.delete(plan_url, headers=bob).status_code == 404
    assert client.get(f"{plan_url}/sessions", headers=bob).status_code == 404
    assert create_session(client, bob, plan_id).status_code == 404
    assert client.get(session_url, headers=bob).status_code == 404
    assert client.get(f"{session_url}/exercises", headers=bob).status_code == 404
    assert prescribe(client, bob, plan_id, session_id, bob_exercise).status_code == 404
    assert (
        client.patch(prescription_url, json={"sets": 9}, headers=bob).status_code == 404
    )
    assert client.delete(prescription_url, headers=bob).status_code == 404

    # Alice's data is untouched.
    assert (
        client.get(prescription_url.rsplit("/", 1)[0], headers=alice).json()[0]["sets"]
        == 3
    )

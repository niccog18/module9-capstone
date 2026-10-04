"""API client for the AI Fitness Tracker backend.

Every call the Streamlit UI makes to the backend goes through this module, so
app.py and the page modules never touch ``requests`` directly. Failures are
raised as ApiError with a message that is safe to show to the user.
"""

import os
from typing import Any

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
API_PREFIX = "/api/v1"

DEFAULT_TIMEOUT_SECONDS = 10
# The backend waits up to 120 s for the local LLM, so allow a little longer.
ASK_TIMEOUT_SECONDS = 130


class ApiError(Exception):
    """A failed backend call, with a message that can be shown to the user."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    @property
    def is_unauthorized(self) -> bool:
        """True when the token is missing, invalid or expired (HTTP 401)."""

        return self.status_code == 401


def _format_detail(response: requests.Response) -> str:
    """Turn an error response into one readable sentence."""

    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None

    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):  # FastAPI/Pydantic validation errors (422)
        messages = []
        for error in detail:
            location = [str(part) for part in error.get("loc", []) if part != "body"]
            field = ".".join(location)
            message = error.get("msg", "Invalid value")
            messages.append(f"{field}: {message}" if field else message)
        return "; ".join(messages) or "The request was invalid."

    return f"The server returned an error ({response.status_code})."


def _request(
    method: str,
    path: str,
    token: str | None = None,
    *,
    json: Any = None,
    data: Any = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    api_path: bool = True,
) -> Any:
    """Send a request and return the decoded JSON body (None for 204)."""

    url = f"{BACKEND_URL}{API_PREFIX if api_path else ''}{path}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            params=params,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise ApiError(
            "The server took too long to respond. Please try again."
        ) from exc
    except requests.ConnectionError as exc:
        raise ApiError(
            "Cannot reach the server. Check that the backend is running."
        ) from exc
    except requests.RequestException as exc:
        raise ApiError("Something went wrong while contacting the server.") from exc

    if response.status_code >= 400:
        raise ApiError(_format_detail(response), response.status_code)

    if response.status_code == 204 or not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("The server returned an unexpected response.") from exc


# --- Health ------------------------------------------------------------------


def health_check() -> dict[str, Any]:
    """Return the /health report. Never raises.

    /health answers 503 with a JSON body when the database is down; that body
    is still returned. If the backend cannot be reached at all, an
    "unreachable" report is returned instead.
    """

    try:
        response = requests.get(
            f"{BACKEND_URL}/health", timeout=DEFAULT_TIMEOUT_SECONDS
        )
        return response.json()
    except (requests.RequestException, ValueError):
        return {
            "status": "unreachable",
            "database": "unknown",
            "ollama": "unknown",
            "chromadb": "unknown",
        }


# --- Authentication ----------------------------------------------------------


def register(username: str, email: str, password: str) -> dict[str, Any]:
    """Create an account."""

    return _request(
        "POST",
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(username: str, password: str) -> str:
    """Log in and return the access token (the login form is form-encoded)."""

    body = _request(
        "POST",
        "/auth/login",
        data={"username": username, "password": password},
    )
    return body["access_token"]


def get_current_user(token: str) -> dict[str, Any]:
    """Return the logged-in user's profile."""

    return _request("GET", "/auth/me", token)


# --- Exercises ---------------------------------------------------------------


def list_exercises(token: str, limit: int = 500, offset: int = 0) -> list[dict]:
    return _request(
        "GET", "/exercises", token, params={"limit": limit, "offset": offset}
    )


def create_exercise(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/exercises", token, json=payload)


def update_exercise(token: str, exercise_id: int, payload: dict[str, Any]) -> dict:
    return _request("PATCH", f"/exercises/{exercise_id}", token, json=payload)


def delete_exercise(token: str, exercise_id: int) -> None:
    _request("DELETE", f"/exercises/{exercise_id}", token)


# --- Workouts ----------------------------------------------------------------


def list_workouts(token: str, limit: int = 100, offset: int = 0) -> list[dict]:
    return _request(
        "GET", "/workouts", token, params={"limit": limit, "offset": offset}
    )


def get_workout(token: str, workout_id: int) -> dict[str, Any]:
    return _request("GET", f"/workouts/{workout_id}", token)


def create_workout(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/workouts", token, json=payload)


def update_workout(token: str, workout_id: int, payload: dict[str, Any]) -> dict:
    return _request("PATCH", f"/workouts/{workout_id}", token, json=payload)


def delete_workout(token: str, workout_id: int) -> None:
    _request("DELETE", f"/workouts/{workout_id}", token)


def add_workout_exercise(
    token: str, workout_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request("POST", f"/workouts/{workout_id}/exercises", token, json=payload)


def update_workout_exercise(
    token: str, workout_id: int, workout_exercise_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "PATCH",
        f"/workouts/{workout_id}/exercises/{workout_exercise_id}",
        token,
        json=payload,
    )


def delete_workout_exercise(
    token: str, workout_id: int, workout_exercise_id: int
) -> None:
    _request("DELETE", f"/workouts/{workout_id}/exercises/{workout_exercise_id}", token)


# --- Plans, sessions and prescriptions ----------------------------------------


def list_plans(token: str, limit: int = 100, offset: int = 0) -> list[dict]:
    return _request("GET", "/plans", token, params={"limit": limit, "offset": offset})


def get_plan(token: str, plan_id: int) -> dict[str, Any]:
    return _request("GET", f"/plans/{plan_id}", token)


def create_plan(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/plans", token, json=payload)


def update_plan(token: str, plan_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("PATCH", f"/plans/{plan_id}", token, json=payload)


def delete_plan(token: str, plan_id: int) -> None:
    _request("DELETE", f"/plans/{plan_id}", token)


def create_session(token: str, plan_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/plans/{plan_id}/sessions", token, json=payload)


def update_session(
    token: str, plan_id: int, session_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "PATCH", f"/plans/{plan_id}/sessions/{session_id}", token, json=payload
    )


def delete_session(token: str, plan_id: int, session_id: int) -> None:
    _request("DELETE", f"/plans/{plan_id}/sessions/{session_id}", token)


def add_prescription(
    token: str, plan_id: int, session_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/plans/{plan_id}/sessions/{session_id}/exercises",
        token,
        json=payload,
    )


def update_prescription(
    token: str,
    plan_id: int,
    session_id: int,
    plan_exercise_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request(
        "PATCH",
        f"/plans/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
        token,
        json=payload,
    )


def delete_prescription(
    token: str, plan_id: int, session_id: int, plan_exercise_id: int
) -> None:
    _request(
        "DELETE",
        f"/plans/{plan_id}/sessions/{session_id}/exercises/{plan_exercise_id}",
        token,
    )


# --- AI assistant ------------------------------------------------------------


def ask(question: str, token: str) -> dict[str, Any]:
    """Ask the RAG assistant. Returns answer, sources, confidence, chunks."""

    return _request(
        "POST",
        "/ask",
        token,
        json={"question": question},
        timeout=ASK_TIMEOUT_SECONDS,
    )

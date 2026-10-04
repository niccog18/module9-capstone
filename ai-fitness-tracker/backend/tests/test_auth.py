"""Capstone backend tests for authentication."""

USER = {
    "username": "pytest_auth_user",
    "email": "pytest_auth_user@example.com",
    "password": "TestPassword123!",
}


def register(client, **overrides):
    return client.post("/api/v1/auth/register", json={**USER, **overrides})


def login(client, username=USER["username"], password=USER["password"]):
    # The login endpoint takes OAuth2 form data, not JSON.
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )


def test_register_creates_user(client):
    """Registering a new user returns the created user without secrets."""

    response = register(client)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == USER["username"]
    assert data["email"] == USER["email"]
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_username_conflicts(client):
    """A second registration with the same username is rejected."""

    assert register(client).status_code == 201

    response = register(client, email="different@example.com")

    assert response.status_code == 409


def test_login_returns_token(client):
    """Valid credentials return a bearer token."""

    register(client)

    response = login(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_rejects_wrong_password(client):
    """A wrong password is rejected with 401."""

    register(client)

    response = login(client, password="WrongPassword123!")

    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    """An unknown username is rejected with 401."""

    response = login(client, username="nobody_here")

    assert response.status_code == 401


def test_protected_route_requires_auth(client):
    """Protected endpoints reject requests without a bearer token."""

    response = client.get("/api/v1/plans")

    assert response.status_code == 401


def test_protected_route_accepts_valid_token(client):
    """The token returned by login grants access to protected endpoints."""

    register(client)
    token = login(client).json()["access_token"]

    response = client.get(
        "/api/v1/plans",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == []

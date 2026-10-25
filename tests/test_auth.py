from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.models import User
from tests.helpers import auth_headers, login, register


def test_register_hides_password_trims_name_and_lowercases_email(client):
    response = register(client, " Alice ", "Alice@Example.com")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice"
    assert body["email"] == "alice@example.com"
    assert set(body) == {"id", "name", "email"}


def test_password_is_stored_as_argon2_hash(client, db_session):
    register(client, "Alice", "alice@example.com", "password123")
    stored = db_session.query(User).one().password_hash
    assert stored.startswith("$argon2")
    assert "password123" not in stored


def test_duplicate_email_is_case_insensitive(client):
    assert register(client, "A", "User@Example.com").status_code == 201
    response = register(client, "B", "user@example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"name": "A", "email": "a@example.com", "password": "short"}, "password"),
        ({"name": "A", "email": "not-an-email", "password": "password123"}, "email"),
        ({"name": "   ", "email": "a@example.com", "password": "password123"}, "name"),
        ({"email": "a@example.com", "password": "password123"}, "name"),
    ],
)
def test_register_validation_errors(client, payload, field):
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in [d["field"] for d in error["details"]]


def test_register_rejects_unknown_fields(client):
    response = client.post(
        "/auth/register",
        json={"name": "A", "email": "a@example.com", "password": "password123", "is_admin": True},
    )
    assert response.status_code == 422


def test_successful_login_returns_usable_token(client):
    register(client, "A", "a@example.com")
    response = login(client, "a@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "a@example.com"
    assert "password" not in str(body).lower().replace("password_", "")
    me = client.get("/projects", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_login_email_is_case_insensitive(client):
    register(client, "A", "a@example.com")
    assert login(client, "A@EXAMPLE.COM").status_code == 200


def test_failed_login_wrong_password(client):
    register(client, "A", "a@example.com")
    response = login(client, "a@example.com", "wrong-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_failed_login_unknown_user_is_indistinguishable_from_wrong_password(client):
    register(client, "A", "a@example.com")
    wrong_password = login(client, "a@example.com", "wrong-password")
    unknown_user = login(client, "nobody@example.com")
    assert unknown_user.status_code == wrong_password.status_code == 401
    assert unknown_user.json() == wrong_password.json()


def test_missing_token_is_rejected(client):
    response = client.get("/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_non_bearer_scheme_is_treated_as_missing_token(client):
    response = client.get("/projects", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_garbage_token_is_rejected(client):
    response = client.get("/projects", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def _token(user_id, expires_in, secret=None):
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + expires_in}
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_expired_token_is_rejected(client):
    register(client, "A", "a@example.com")
    token = _token(1, timedelta(minutes=-5))
    response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_token_signed_with_other_secret_is_rejected(client):
    register(client, "A", "a@example.com")
    token = _token(1, timedelta(minutes=5), secret="another-secret-that-is-also-long-enough!!")
    response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_for_nonexistent_user_is_rejected(client):
    token = _token(9999, timedelta(minutes=5))
    response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


PROTECTED = [
    ("post", "/projects"),
    ("get", "/projects"),
    ("get", "/projects/1"),
    ("post", "/projects/1/members"),
    ("delete", "/projects/1"),
    ("post", "/projects/1/tasks"),
    ("get", "/projects/1/tasks"),
    ("get", "/projects/1/summary"),
    ("patch", "/tasks/1"),
    ("delete", "/tasks/1"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_every_project_and_task_endpoint_requires_authentication(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401, f"{method.upper()} {path} is not protected"
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_auth_headers_helper_roundtrip(client):
    register(client, "A", "a@example.com")
    assert client.get("/projects", headers=auth_headers(client, "a@example.com")).status_code == 200

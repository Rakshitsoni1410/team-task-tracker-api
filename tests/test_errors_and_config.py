import pytest
from pydantic import ValidationError

from app.config import DEFAULT_JWT_SECRET, Settings
from app.services import project_service


def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_uses_standard_error_shape(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_uses_standard_error_shape(client):
    response = client.put("/auth/login")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_malformed_json_body_is_a_validation_error(client):
    response = client.post("/auth/login", content="{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unexpected_exception_returns_generic_500_without_leaking_details(client, users, monkeypatch, caplog):
    def explode(*_, **__):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(project_service, "list_for_user", explode)
    response = client.get("/projects", headers=users["owner"])
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret internal detail" not in response.text
    assert "secret internal detail" in caplog.text  # ...but it IS logged server-side


def test_every_error_response_has_the_same_shape(client, users, project):
    responses = [
        client.get("/projects"),  # 401
        client.get(f"/projects/{project['id']}", headers=users["other"]),  # 403
        client.get("/projects/9999", headers=users["owner"]),  # 404
        client.post("/auth/register", json={}),  # 422
        client.post("/auth/login", json={"email": "x@example.com", "password": "nope-nope"}),  # 401
    ]
    for response in responses:
        assert response.status_code >= 400
        error = response.json()["error"]
        assert isinstance(error["code"], str) and isinstance(error["message"], str)


# -------------------------------------------------------------------- config
def test_default_secret_is_accepted_only_in_development(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert Settings(_env_file=None, app_env="development").jwt_secret == DEFAULT_JWT_SECRET
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production")


def test_short_or_placeholder_secret_is_rejected_in_production():
    for secret in ("too-short", "replace-this-with-a-long-random-secret"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, app_env="production", jwt_secret=secret)


def test_strong_secret_is_accepted_in_production():
    settings = Settings(_env_file=None, app_env="production", jwt_secret="x" * 48)
    assert settings.app_env == "production"

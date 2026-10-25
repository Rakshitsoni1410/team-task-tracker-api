"""Shared fixtures.

By default the suite runs on in-memory SQLite (fast, zero setup). Set TEST_DATABASE_URL to a
PostgreSQL URL to run the identical suite against the production database engine; CI does both.
"""
import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.security as security  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import auth_headers, register, task_payload  # noqa: E402

IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
else:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def fast_password_hashing():
    """Argon2 with production cost makes the suite needlessly slow; hashes stay argon2."""
    cheap = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    security._hasher = cheap
    security._DUMMY_HASH = cheap.hash("timing-equalisation-placeholder")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def users(client):
    register(client, "Owner", "owner@example.com")
    register(client, "Member", "member@example.com")
    register(client, "Other", "other@example.com")
    return {
        "owner": auth_headers(client, "owner@example.com"),
        "member": auth_headers(client, "member@example.com"),
        "other": auth_headers(client, "other@example.com"),
    }


@pytest.fixture
def project(client, users):
    """A project owned by `owner` with `member` added; `other` is NOT a member."""
    created = client.post(
        "/projects",
        headers=users["owner"],
        json={"name": "Backend Internship", "description": "Task tracker project"},
    ).json()
    client.post(
        f"/projects/{created['id']}/members", headers=users["owner"], json={"email": "member@example.com"}
    )
    return created


@pytest.fixture
def make_task(client, project):
    def _make(headers, **overrides):
        response = client.post(
            f"/projects/{project['id']}/tasks", headers=headers, json=task_payload(**overrides)
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make

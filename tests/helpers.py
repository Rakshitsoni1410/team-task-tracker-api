from datetime import UTC, datetime, timedelta


def future_date(days: int = 3) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def past_date(days: int = 3) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def register(client, name, email, password="password123"):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


def login(client, email, password="password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_headers(client, email, password="password123"):
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def task_payload(title="A task", priority="MEDIUM", due_date=None, **extra):
    return {"title": title, "priority": priority, "due_date": due_date or future_date(), **extra}

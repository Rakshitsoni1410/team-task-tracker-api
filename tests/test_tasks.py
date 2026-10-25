import pytest

from tests.helpers import future_date, past_date, task_payload


def _create(client, project, headers, **kwargs):
    return client.post(f"/projects/{project['id']}/tasks", headers=headers, json=task_payload(**kwargs))


# ----------------------------------------------------------------- creation
def test_member_creates_task_with_defaults(client, users, project):
    response = _create(client, project, users["member"], title="  Write docs  ", description="d")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write docs"
    assert body["status"] == "TODO"
    assert body["completed_at"] is None
    assert body["assignee"] is None
    assert body["creator"]["email"] == "member@example.com"
    assert body["created_at"] and body["updated_at"]


def test_non_member_cannot_create_task(client, users, project):
    assert _create(client, project, users["other"]).status_code == 403


def test_create_task_in_unknown_project_returns_404(client, users):
    response = client.post("/projects/99999/tasks", headers=users["owner"], json=task_payload())
    assert response.status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"priority": "URGENT"},
        {"due_date": "not-a-date"},
        {"assignee_email": "not-an-email"},
        {"status": "DONE"},  # status is not accepted on create
    ],
)
def test_create_task_validation(client, users, project, overrides):
    response = _create(client, project, users["owner"], **overrides)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_task_requires_due_date_and_priority(client, users, project):
    response = client.post(f"/projects/{project['id']}/tasks", headers=users["owner"], json={"title": "x"})
    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert {"priority", "due_date"} <= fields


def test_past_due_dates_are_allowed(client, users, project):
    response = _create(client, project, users["owner"], due_date=past_date(30))
    assert response.status_code == 201


def test_naive_due_date_is_treated_as_utc(client, users, project):
    response = _create(client, project, users["owner"], due_date="2030-01-15T10:00:00")
    assert response.json()["due_date"] == "2030-01-15T10:00:00Z"


def test_due_date_with_offset_is_converted_to_utc(client, users, project):
    response = _create(client, project, users["owner"], due_date="2030-01-15T10:00:00+05:30")
    assert response.json()["due_date"] == "2030-01-15T04:30:00Z"


# ----------------------------------------------------------------- assignee
def test_assignee_who_is_member_is_accepted(client, users, project):
    response = _create(client, project, users["owner"], assignee_email="member@example.com")
    assert response.status_code == 201
    assert response.json()["assignee"]["email"] == "member@example.com"


def test_assignee_who_is_not_a_member_is_rejected(client, users, project):
    response = _create(client, project, users["owner"], assignee_email="other@example.com")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ASSIGNEE"


def test_assignee_who_is_not_registered_is_rejected(client, users, project):
    response = _create(client, project, users["owner"], assignee_email="ghost@example.com")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ASSIGNEE"


def test_invalid_assignee_on_update_is_rejected_and_task_unchanged(client, users, project, make_task):
    task = make_task(users["owner"], assignee_email="member@example.com")
    response = client.patch(
        f"/tasks/{task['id']}", headers=users["owner"], json={"assignee_email": "other@example.com"}
    )
    assert response.status_code == 400
    listing = client.get(f"/projects/{project['id']}/tasks", headers=users["owner"]).json()
    assert listing["items"][0]["assignee"]["email"] == "member@example.com"


# ------------------------------------------------------------------- update
def test_patch_changes_only_supplied_fields(client, users, make_task):
    task = make_task(users["owner"], title="Original", description="keep me", priority="LOW")
    response = client.patch(f"/tasks/{task['id']}", headers=users["member"], json={"priority": "HIGH"})
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "HIGH"
    assert body["title"] == "Original"
    assert body["description"] == "keep me"
    assert body["due_date"] == task["due_date"]


def test_patch_null_description_clears_it(client, users, make_task):
    task = make_task(users["owner"], description="to be removed")
    response = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_patch_null_assignee_unassigns(client, users, project, make_task):
    task = make_task(users["owner"], assignee_email="member@example.com")
    response = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"assignee_email": None})
    assert response.status_code == 200
    assert response.json()["assignee"] is None
    # ...and it is really persisted, not just reflected in the response
    listing = client.get(f"/projects/{project['id']}/tasks", headers=users["owner"]).json()
    assert listing["items"][0]["assignee"] is None


def test_patch_omitted_assignee_is_left_alone(client, users, make_task):
    task = make_task(users["owner"], assignee_email="member@example.com")
    response = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"title": "Renamed"})
    assert response.json()["assignee"]["email"] == "member@example.com"


@pytest.mark.parametrize(
    "body",
    [
        {"title": None},
        {"title": "   "},
        {"priority": None},
        {"status": None},
        {"status": "FINISHED"},
        {"due_date": None},
        {"assignee": "member@example.com"},  # misspelt field must not be silently ignored
    ],
)
def test_patch_validation_errors(client, users, make_task, body):
    task = make_task(users["owner"])
    response = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_member_cannot_patch_task(client, users, make_task):
    task = make_task(users["owner"])
    response = client.patch(f"/tasks/{task['id']}", headers=users["other"], json={"title": "hacked"})
    assert response.status_code == 403


def test_patch_unknown_task_returns_404(client, users):
    response = client.patch("/tasks/999999", headers=users["owner"], json={"title": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


# -------------------------------------------------------------- completed_at
def test_completed_at_is_set_when_task_becomes_done(client, users, make_task):
    task = make_task(users["owner"])
    assert task["completed_at"] is None
    done = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE"})
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None


def test_completed_at_is_cleared_when_task_is_reopened(client, users, make_task):
    task = make_task(users["owner"])
    client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE"})
    reopened = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "IN_PROGRESS"})
    assert reopened.json()["completed_at"] is None


def test_completed_at_is_not_overwritten_by_later_edits_while_done(client, users, make_task):
    task = make_task(users["owner"])
    first = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE"}).json()
    edited = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"title": "Edited"}).json()
    again = client.patch(
        f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE", "title": "Edited 2"}
    ).json()
    assert first["completed_at"] == edited["completed_at"] == again["completed_at"]


def test_completed_at_is_set_again_after_reopen_and_redo(client, users, make_task):
    task = make_task(users["owner"])
    client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE"})
    client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "TODO"})
    redone = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"status": "DONE"})
    assert redone.json()["completed_at"] is not None


def test_updated_at_does_not_go_backwards(client, users, make_task):
    task = make_task(users["owner"])
    updated = client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"title": "New"}).json()
    assert updated["updated_at"] >= task["updated_at"]
    assert updated["created_at"] == task["created_at"]


# ------------------------------------------------------------------- delete
def test_task_creator_can_delete_own_task(client, users, make_task):
    task = make_task(users["member"])
    assert client.delete(f"/tasks/{task['id']}", headers=users["member"]).status_code == 204


def test_project_owner_can_delete_any_task(client, users, make_task):
    task = make_task(users["member"])
    assert client.delete(f"/tasks/{task['id']}", headers=users["owner"]).status_code == 204
    assert client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"title": "x"}).status_code == 404


def test_regular_member_cannot_delete_someone_elses_task(client, users, make_task):
    task = make_task(users["owner"])
    response = client.delete(f"/tasks/{task['id']}", headers=users["member"])
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_non_member_cannot_delete_task(client, users, make_task):
    task = make_task(users["owner"])
    assert client.delete(f"/tasks/{task['id']}", headers=users["other"]).status_code == 403


def test_delete_unknown_task_returns_404(client, users):
    assert client.delete("/tasks/999999", headers=users["owner"]).status_code == 404


def test_future_date_helper_is_in_the_future():
    assert future_date() > past_date()

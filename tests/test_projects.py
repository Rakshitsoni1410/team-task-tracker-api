from tests.helpers import task_payload


def test_creator_becomes_owner_and_member(client, users):
    response = client.post("/projects", headers=users["owner"], json={"name": "  Launch  "})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Launch"
    assert body["description"] is None
    assert body["owner"]["email"] == "owner@example.com"
    assert [m["email"] for m in body["members"]] == ["owner@example.com"]


def test_blank_project_name_is_rejected(client, users):
    response = client.post("/projects", headers=users["owner"], json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_projects_only_returns_projects_the_user_belongs_to(client, users, project):
    assert [p["id"] for p in client.get("/projects", headers=users["owner"]).json()] == [project["id"]]
    assert [p["id"] for p in client.get("/projects", headers=users["member"]).json()] == [project["id"]]
    assert client.get("/projects", headers=users["other"]).json() == []


def test_member_can_view_project(client, users, project):
    response = client.get(f"/projects/{project['id']}", headers=users["member"])
    assert response.status_code == 200
    emails = {m["email"] for m in response.json()["members"]}
    assert emails == {"owner@example.com", "member@example.com"}


def test_non_member_cannot_view_project(client, users, project):
    response = client.get(f"/projects/{project['id']}", headers=users["other"])
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_non_member_cannot_modify_project_data(client, users, project, make_task):
    task = make_task(users["owner"])
    pid = project["id"]
    assert client.post(f"/projects/{pid}/tasks", headers=users["other"], json=task_payload()).status_code == 403
    assert client.get(f"/projects/{pid}/tasks", headers=users["other"]).status_code == 403
    assert client.get(f"/projects/{pid}/summary", headers=users["other"]).status_code == 403
    assert client.patch(f"/tasks/{task['id']}", headers=users["other"], json={"title": "x"}).status_code == 403
    assert client.delete(f"/tasks/{task['id']}", headers=users["other"]).status_code == 403


def test_unknown_project_returns_404(client, users):
    response = client.get("/projects/999999", headers=users["owner"])
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_owner_can_add_member_by_email_case_insensitively(client, users, project):
    response = client.post(
        f"/projects/{project['id']}/members", headers=users["owner"], json={"email": "OTHER@Example.com"}
    )
    assert response.status_code == 200
    assert "other@example.com" in {m["email"] for m in response.json()["members"]}
    assert client.get(f"/projects/{project['id']}", headers=users["other"]).status_code == 200


def test_only_owner_can_add_member(client, users, project):
    response = client.post(
        f"/projects/{project['id']}/members", headers=users["member"], json={"email": "other@example.com"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_add_unregistered_user_returns_404(client, users, project):
    response = client.post(
        f"/projects/{project['id']}/members", headers=users["owner"], json={"email": "ghost@example.com"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_adding_existing_member_returns_409(client, users, project):
    response = client.post(
        f"/projects/{project['id']}/members", headers=users["owner"], json={"email": "member@example.com"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_MEMBER"


def test_member_cannot_delete_project(client, users, project):
    assert client.delete(f"/projects/{project['id']}", headers=users["member"]).status_code == 403
    assert client.get(f"/projects/{project['id']}", headers=users["owner"]).status_code == 200


def test_owner_can_delete_project_and_its_tasks_are_removed(client, users, project, make_task):
    task = make_task(users["owner"])
    assert client.delete(f"/projects/{project['id']}", headers=users["owner"]).status_code == 204
    assert client.get(f"/projects/{project['id']}", headers=users["owner"]).status_code == 404
    assert client.patch(f"/tasks/{task['id']}", headers=users["owner"], json={"title": "x"}).status_code == 404
    assert client.get("/projects", headers=users["member"]).json() == []

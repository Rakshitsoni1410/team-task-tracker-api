import pytest

from tests.helpers import task_payload


def _url(project):
    return f"/projects/{project['id']}/tasks"


def _titles(response):
    return [t["title"] for t in response.json()["items"]]


# ---------------------------------------------------------------- pagination
def test_default_page_size_is_10_and_metadata_is_correct(client, users, project, make_task):
    for i in range(25):
        make_task(users["owner"], title=f"T{i:02d}")
    page1 = client.get(_url(project), headers=users["owner"]).json()
    assert (page1["page"], page1["page_size"], page1["total"], page1["pages"]) == (1, 10, 25, 3)
    assert len(page1["items"]) == 10
    page3 = client.get(_url(project), params={"page": 3}, headers=users["owner"]).json()
    assert len(page3["items"]) == 5


def test_pages_do_not_overlap_or_skip_rows(client, users, project, make_task):
    for i in range(12):
        make_task(users["owner"], title=f"T{i:02d}")
    seen = []
    for page in (1, 2, 3):
        body = client.get(_url(project), params={"page": page, "page_size": 5}, headers=users["owner"]).json()
        seen += [t["id"] for t in body["items"]]
    assert len(seen) == len(set(seen)) == 12


def test_page_beyond_last_returns_empty_items(client, users, project, make_task):
    make_task(users["owner"])
    body = client.get(_url(project), params={"page": 50}, headers=users["owner"]).json()
    assert body["items"] == [] and body["total"] == 1


def test_max_page_size_is_50(client, users, project, make_task):
    for i in range(55):
        make_task(users["owner"], title=f"T{i}")
    ok = client.get(_url(project), params={"page_size": 50}, headers=users["owner"])
    assert ok.status_code == 200 and len(ok.json()["items"]) == 50


@pytest.mark.parametrize("params", [{"page_size": 51}, {"page_size": 0}, {"page": 0}, {"page": "abc"}])
def test_invalid_pagination_parameters_are_rejected(client, users, project, params):
    response = client.get(_url(project), params=params, headers=users["owner"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------- filters
def test_filter_by_status(client, users, project, make_task):
    done = make_task(users["owner"], title="done one")
    make_task(users["owner"], title="todo one")
    client.patch(f"/tasks/{done['id']}", headers=users["owner"], json={"status": "DONE"})
    response = client.get(_url(project), params={"status": "DONE"}, headers=users["owner"])
    assert _titles(response) == ["done one"]


def test_filter_by_priority(client, users, project, make_task):
    make_task(users["member"], title="High task", priority="HIGH")
    make_task(users["member"], title="Low task", priority="LOW")
    response = client.get(_url(project), params={"priority": "HIGH"}, headers=users["owner"])
    assert response.json()["total"] == 1 and _titles(response) == ["High task"]


def test_filter_by_assignee_email_case_insensitively(client, users, project, make_task):
    make_task(users["owner"], title="mine", assignee_email="owner@example.com")
    make_task(users["owner"], title="theirs", assignee_email="member@example.com")
    make_task(users["owner"], title="nobody's")
    response = client.get(_url(project), params={"assignee": "MEMBER@example.com"}, headers=users["owner"])
    assert _titles(response) == ["theirs"]


def test_filter_by_unknown_assignee_returns_empty_page(client, users, project, make_task):
    make_task(users["owner"])
    response = client.get(_url(project), params={"assignee": "ghost@example.com"}, headers=users["owner"])
    assert response.status_code == 200
    assert response.json()["items"] == [] and response.json()["total"] == 0


def test_filters_combine_with_and(client, users, project, make_task):
    make_task(users["owner"], title="match", priority="HIGH", assignee_email="member@example.com")
    make_task(users["owner"], title="wrong prio", priority="LOW", assignee_email="member@example.com")
    make_task(users["owner"], title="wrong assignee", priority="HIGH", assignee_email="owner@example.com")
    response = client.get(
        _url(project), params={"priority": "HIGH", "assignee": "member@example.com", "status": "TODO"},
        headers=users["owner"],
    )
    assert _titles(response) == ["match"]


def test_due_date_range_filter_is_inclusive(client, users, project, make_task):
    for day in (10, 15, 20, 25):
        make_task(users["owner"], title=f"day{day}", due_date=f"2030-01-{day}T12:00:00Z")
    response = client.get(
        _url(project),
        params={
            "due_from": "2030-01-15T12:00:00Z",
            "due_to": "2030-01-20T12:00:00Z",
            "sort_by": "due_date",
            "sort_order": "asc",
        },
        headers=users["owner"],
    )
    assert _titles(response) == ["day15", "day20"]


def test_due_date_range_respects_timezone_offsets(client, users, project, make_task):
    # 12:00+05:30 is 06:30Z, which is BEFORE 08:00Z even though "12:00" > "08:00" as text.
    make_task(users["owner"], title="early", due_date="2030-01-15T12:00:00+05:30")
    make_task(users["owner"], title="late", due_date="2030-01-15T09:00:00Z")
    response = client.get(
        _url(project), params={"due_from": "2030-01-15T08:00:00Z"}, headers=users["owner"]
    )
    assert _titles(response) == ["late"]


def test_inverted_due_date_range_is_rejected(client, users, project):
    response = client.get(
        _url(project),
        params={"due_from": "2030-02-01T00:00:00Z", "due_to": "2030-01-01T00:00:00Z"},
        headers=users["owner"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_invalid_filter_values_are_rejected(client, users, project):
    for params in ({"status": "NOPE"}, {"priority": "NOPE"}, {"due_from": "yesterday"}):
        assert client.get(_url(project), params=params, headers=users["owner"]).status_code == 422


def test_listing_never_includes_tasks_from_other_projects(client, users, project, make_task):
    make_task(users["owner"], title="in project")
    other = client.post("/projects", headers=users["owner"], json={"name": "Other"}).json()
    client.post(f"/projects/{other['id']}/tasks", headers=users["owner"], json=task_payload(title="elsewhere"))
    assert _titles(client.get(_url(project), headers=users["owner"])) == ["in project"]


# ------------------------------------------------------------------- sorting
def test_sort_by_due_date_ascending_and_descending(client, users, project, make_task):
    for title, due in [("b", "2030-02-01T00:00:00Z"), ("a", "2030-01-01T00:00:00Z"), ("c", "2030-03-01T00:00:00Z")]:
        make_task(users["owner"], title=title, due_date=due)
    asc = client.get(_url(project), params={"sort_by": "due_date", "sort_order": "asc"}, headers=users["owner"])
    desc = client.get(_url(project), params={"sort_by": "due_date", "sort_order": "desc"}, headers=users["owner"])
    assert _titles(asc) == ["a", "b", "c"]
    assert _titles(desc) == ["c", "b", "a"]


def test_sort_by_created_at_both_directions(client, users, project, make_task):
    for title in ("first", "second", "third"):
        make_task(users["owner"], title=title)
    asc = client.get(_url(project), params={"sort_by": "created_at", "sort_order": "asc"}, headers=users["owner"])
    desc = client.get(_url(project), headers=users["owner"])  # default: newest first
    assert _titles(asc) == ["first", "second", "third"]
    assert _titles(desc) == ["third", "second", "first"]


@pytest.mark.parametrize("params", [{"sort_by": "title"}, {"sort_order": "sideways"}])
def test_invalid_sort_parameters_are_rejected(client, users, project, params):
    assert client.get(_url(project), params=params, headers=users["owner"]).status_code == 422


def test_listing_is_forbidden_for_non_members_and_404_for_unknown_project(client, users, project):
    assert client.get(_url(project), headers=users["other"]).status_code == 403
    assert client.get("/projects/99999/tasks", headers=users["owner"]).status_code == 404


# ------------------------------------------------------------------- summary
def test_summary_of_empty_project_lists_every_bucket_with_zero(client, users, project):
    body = client.get(f"/projects/{project['id']}/summary", headers=users["owner"]).json()
    assert body == {
        "total": 0,
        "by_status": {"TODO": 0, "IN_PROGRESS": 0, "DONE": 0},
        "by_priority": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
    }


def test_summary_counts_by_status_and_priority(client, users, project, make_task):
    a = make_task(users["owner"], priority="HIGH")
    b = make_task(users["owner"], priority="HIGH")
    make_task(users["owner"], priority="LOW")
    client.patch(f"/tasks/{a['id']}", headers=users["owner"], json={"status": "DONE"})
    client.patch(f"/tasks/{b['id']}", headers=users["owner"], json={"status": "IN_PROGRESS"})
    body = client.get(f"/projects/{project['id']}/summary", headers=users["member"]).json()
    assert body["total"] == 3
    assert body["by_status"] == {"TODO": 1, "IN_PROGRESS": 1, "DONE": 1}
    assert body["by_priority"] == {"LOW": 1, "MEDIUM": 0, "HIGH": 2}


def test_summary_only_counts_the_requested_project(client, users, project, make_task):
    make_task(users["owner"])
    other = client.post("/projects", headers=users["owner"], json={"name": "Other"}).json()
    for _ in range(3):
        client.post(f"/projects/{other['id']}/tasks", headers=users["owner"], json=task_payload())
    assert client.get(f"/projects/{project['id']}/summary", headers=users["owner"]).json()["total"] == 1


def test_summary_requires_membership(client, users, project):
    assert client.get(f"/projects/{project['id']}/summary", headers=users["other"]).status_code == 403
    assert client.get("/projects/99999/summary", headers=users["owner"]).status_code == 404

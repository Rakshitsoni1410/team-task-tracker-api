# Team Task Tracker API

REST API for managing projects, project membership and tasks, built for the Axionix Backend Engineering
Internship assignment. Authentication, per-project authorization, task filtering/sorting/pagination, a summary
endpoint, migrations, 126 automated tests and live Swagger documentation are included. No frontend.

- **Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 (SQLite supported) · Alembic · PyJWT · Argon2 · pytest
- **API documentation:** Swagger UI at `http://localhost:8000/docs` · OpenAPI JSON at `/openapi.json`
  (importable into Postman or Bruno via *Import → Link*).

---

## 1. Run it

Pick **one** of the three options. Each is self-contained.

### Option A - Docker Compose (API + PostgreSQL, nothing else to install)

Prerequisite: Docker with Compose v2.

```bash
docker compose up --build
```

The `api` container waits for the database, runs `alembic upgrade head`, then starts the server on port 8000.
No `.env` file is needed. To use your own secret: `JWT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))") docker compose up --build`.

### Option B - Native, PostgreSQL

Prerequisites: Python 3.12, PostgreSQL 14+.

```bash
# 1. database (once)
psql -U postgres -c "CREATE USER tasktracker WITH PASSWORD 'tasktracker';"
psql -U postgres -c "CREATE DATABASE tasktracker OWNER tasktracker;"

# 2. app
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                     # defaults already match step 1
alembic upgrade head
uvicorn app.main:app --reload
```

### Option C - Native, SQLite (zero database setup)

Prerequisite: Python 3.12.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# edit .env:  DATABASE_URL=sqlite:///./tasktracker.db
alembic upgrade head
uvicorn app.main:app --reload
```

SQLite is fine for evaluation. For production use PostgreSQL: SQLite has no real concurrency, stores timestamps
without time zone information (the API normalises everything to UTC to compensate) and cannot add many kinds of
constraint after the fact.

### Optional demo data

```bash
python -m scripts.seed
```

Creates `asha@`, `ben@` and `chen@example.com` (password `Password123!`) and a *Website Launch* project with four
tasks. `chen` is deliberately **not** a member, which makes it easy to demonstrate adding a member and a 403.
Safe to run twice.

## 2. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local PostgreSQL | SQLAlchemy URL (`postgresql+psycopg://…` or `sqlite:///./file.db`) |
| `JWT_SECRET` | dev-only placeholder | Signs access tokens. **The app refuses to start** if `APP_ENV` is anything other than `development`/`test` and the secret is a placeholder or shorter than 32 characters |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `APP_ENV` | `development` | `development`, `test`, `production`, … |
| `APP_NAME` | `Team Task Tracker API` | Shown in Swagger |

Secrets live in the environment. `.env` is git-ignored; only `.env.example` is committed.

## 3. Tests

```bash
pip install -r requirements-dev.txt
pytest -q                      # 126 tests, ~8 s, in-memory SQLite, no setup

# Same suite against PostgreSQL (what CI also does):
TEST_DATABASE_URL=postgresql+psycopg://tasktracker:tasktracker@localhost:5432/tasktracker_test pytest -q

ruff check .                   # lint
```

| File | What it proves |
|---|---|
| `test_auth.py` | register/login success and failure, password hashed (argon2) and never returned, expired/forged/garbage/missing tokens, **every** protected endpoint rejects anonymous calls |
| `test_projects.py` | owner = member, non-member blocked from every read and write, owner-only member add / delete, cascade on delete |
| `test_tasks.py` | creation rules, invalid assignee (create *and* update), PATCH semantics, `completed_at` set / preserved / cleared / re-set, delete authorization, UTC handling |
| `test_listing.py` | pagination (default 10, max 50, no overlap), every filter and combinations, due-date range incl. time-zone offsets, sorting both directions, summary |
| `test_database.py` | constraints enforced by the database itself: unique e-mail, unique membership, `completed_at` only when `DONE`, foreign keys |
| `test_migrations.py` | migration builds the expected tables, **matches the models with zero drift**, downgrades cleanly |
| `test_errors_and_config.py` | uniform error shape (incl. 404/405/500), no internal details leaked, production secret guard |

## 4. API

All endpoints except `/auth/*` and `/health` require `Authorization: Bearer <token>`.

| Method | Endpoint | Purpose | Who |
|---|---|---|---|
| POST | `/auth/register` | Create user → 201 | anyone |
| POST | `/auth/login` | Returns JWT | anyone |
| POST | `/projects` | Create project (creator = owner + member) | user |
| GET | `/projects` | Projects the user belongs to | user |
| GET | `/projects/{projectId}` | Project + members | member |
| POST | `/projects/{projectId}/members` | Add registered user by e-mail | **owner** |
| DELETE | `/projects/{projectId}` | Delete project and its tasks → 204 | **owner** |
| POST | `/projects/{projectId}/tasks` | Create task → 201 | member |
| GET | `/projects/{projectId}/tasks` | Paginated, filtered, sorted list | member |
| PATCH | `/tasks/{taskId}` | Partial update | member |
| DELETE | `/tasks/{taskId}` | Delete task → 204 | **owner or task creator** |
| GET | `/projects/{projectId}/summary` | Total + counts by status and priority | member |
| GET | `/health` | Liveness | anyone |

**List parameters** (`GET /projects/{id}/tasks`): `page` (≥1, default 1), `page_size` (1-50, default 10),
`status`, `priority`, `assignee` (e-mail), `due_from`, `due_to` (inclusive, ISO-8601), `sort_by`
(`created_at` \| `due_date`, default `created_at`), `sort_order` (`asc` \| `desc`, default `desc`).
Response: `{items, page, page_size, total, pages}`.
*Tip:* in a URL, a `+` in a UTC offset must be sent as `%2B` (curl: `--data-urlencode`).

### Example session

```bash
B=http://localhost:8000

curl -s -X POST $B/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Asha Patel","email":"asha@example.com","password":"password123"}'

TOKEN=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"asha@example.com","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $B/projects -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Launch","description":"Launch checklist"}'

curl -s -X POST $B/projects/1/tasks -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Ship API","priority":"HIGH","due_date":"2026-12-01T18:00:00Z","assignee_email":"asha@example.com"}'

curl -s -X PATCH $B/tasks/1 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"DONE"}'                      # sets completed_at; any other status clears it

curl -s "$B/projects/1/tasks?status=DONE&sort_by=due_date&sort_order=asc" -H "Authorization: Bearer $TOKEN"
curl -s  $B/projects/1/summary -H "Authorization: Bearer $TOKEN"
```

### Errors

Every error, including unknown routes and unexpected failures, has one shape:

```json
{ "error": { "code": "FORBIDDEN", "message": "You are not a member of this project" } }
```

Validation errors (422) add `details: [{field, message}]`.

| Status | `code` | When |
|---|---|---|
| 400 | `INVALID_ASSIGNEE`, `INVALID_DATE_RANGE` | assignee not a member of the project; `due_from` > `due_to` |
| 401 | `MISSING_TOKEN`, `INVALID_TOKEN`, `INVALID_CREDENTIALS` | no / bad / expired token; wrong e-mail or password |
| 403 | `FORBIDDEN` | not a member, or owner/creator-only action |
| 404 | `PROJECT_NOT_FOUND`, `TASK_NOT_FOUND`, `USER_NOT_FOUND`, `NOT_FOUND` | resource or route does not exist |
| 405 | `METHOD_NOT_ALLOWED` | wrong HTTP method |
| 409 | `DUPLICATE_EMAIL`, `ALREADY_MEMBER` | uniqueness conflicts |
| 422 | `VALIDATION_ERROR` | invalid body or query parameters |
| 500 | `INTERNAL_SERVER_ERROR` | unexpected; generic message, full traceback only in the server log |

## 5. Architecture

```text
app/
  main.py          app wiring, exception handlers
  routers/         HTTP only: parse request, call a service, shape the response
  services/        business rules and authorization decisions (membership, ownership, completed_at…)
  repositories/    all SQL; no business rules
  models.py        SQLAlchemy tables, constraints and indexes
  schemas.py       Pydantic request/response models and input normalisation
  security.py      Argon2 hashing, JWT creation/verification
  deps.py          get_current_user dependency (authentication)
  errors.py        AppError + handlers that give every error the same JSON shape
  config.py        environment-driven settings, production secret guard
  timeutils.py     UTC normalisation
alembic/versions/  migrations (0001_initial)
scripts/seed.py    optional demo data
tests/             126 tests
```

Request flow: *router* → `get_current_user` (401 if no/invalid token) → *service* (404 → 403 → business rules)
→ *repository* (SQL) → response schema. Routers contain no rules and repositories contain no `if user is owner`,
so a rule change touches one place.

**Schema:** `users` ← `projects.owner_id`; `project_members(project_id, user_id)` composite PK;
`tasks(project_id, creator_id, assignee_id, …)`. Deleting a project cascades to its members and tasks at the
database level. Task queries are always project-scoped, so every task index leads with `project_id`
(`status`, `priority`, `assignee_id`, `due_date`, `created_at`); `project_members.user_id` is indexed for
"my projects". A `CHECK` constraint guarantees `completed_at` is only ever set while status is `DONE`.

## 6. Assumptions and design decisions

1. **Past due dates are allowed** (importing overdue work is a normal use case). Tested.
2. **All timestamps are UTC.** Input with an offset is converted; input without one is interpreted as UTC;
   output always ends in `Z`/`+00:00`. This keeps filtering and sorting correct on SQLite too.
3. **E-mail is lower-cased before storage**, so a plain unique index gives case-insensitive uniqueness; login and
   "add member" lookups lower-case as well.
4. **Non-members get 403, not 404, for an existing project.** Clearer for API users; the trade-off is that it
   confirms a project id exists. Unknown ids return 404. Switching to "404 for both" is a one-line change in
   `project_service.require_member`.
5. **Unknown / non-member assignee → 400 `INVALID_ASSIGNEE`**, on create and on update.
6. **`priority` and `due_date` are required on task creation** (the brief lists only description and assignee as
   optional). New tasks always start as `TODO`.
7. **PATCH:** only supplied fields change. `{"assignee_email": null}` unassigns, `{"description": null}` clears the
   description; `null` for `title`, `priority`, `status` or `due_date` is a 422. Unknown fields are a 422 so typos
   are not silently ignored.
8. **`completed_at`** is set when a task *enters* `DONE`, left untouched by later edits while it stays `DONE`, and
   cleared when it leaves `DONE`.
9. Filtering by an unknown assignee e-mail returns an empty page rather than an error.
10. Passwords: 8-128 characters, hashed with Argon2id. Login performs a dummy hash check for unknown e-mails so
    response time does not reveal which e-mails exist.

## 7. Known limitations

- Access tokens are stateless: no refresh tokens, no revocation (a token stays valid until it expires), no rate limiting.
- No endpoints for removing a member, transferring ownership, or deleting/updating a user (not required by the brief).
- `GET /projects` is not paginated.
- No audit log of task changes.
- Not verified under concurrent load; the unique index and primary keys are the guards against races on registration and membership.

## 8. Bonus items included

Docker Compose (API + PostgreSQL) · GitHub Actions: lint, tests on SQLite, and tests plus migration up/down/up on a
PostgreSQL service container · task-query indexes and a migration-drift test · production secret guard · seed script.

## 9. Common changes

| I want to… | Edit |
|---|---|
| Reject past due dates | validator on `due_date` in `schemas.TaskCreate` / `TaskUpdate` |
| Change who may delete tasks | `task_service.delete` |
| Change page-size limits | `page_size` in `routers/projects.list_tasks` |
| Add a column | edit `models.py`, then `alembic revision --autogenerate -m "…"`, then `alembic upgrade head` |

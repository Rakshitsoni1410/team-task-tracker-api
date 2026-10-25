# AI Usage Disclosure

AI tools were used on this project. I am responsible for every line submitted and can explain and change it.

> **Before submitting, replace each `TODO(you)` line with your own words.** This file is only valuable to a
> reviewer if it is *your* honest account. Everything not marked TODO below is a factual record of work that was
> done and checked by running commands/tests.

## Tools used

| Tool | Used for |
|---|---|
| ChatGPT | Initial project scaffold: structure, models, schemas, routes, first tests, first README. *TODO(you): confirm this is accurate, and add any other tool (Copilot, Cursor, …) you used.* |
| Claude (Anthropic) | A review-and-hardening pass over the scaffold: finding defects, fixing them, writing most of the test-suite, CI, Docker hardening, README rewrite. |

## Example prompts / use cases

- "Design a FastAPI + PostgreSQL schema for users, projects, membership and tasks." *(scaffold)*
- "Review this project against the assignment brief like a senior engineering manager, and fix everything."
  *(hardening pass)*
- *TODO(you): add 2-3 prompts you actually wrote.*

## What AI generated

- Layered structure (routers / services / repositories), models, Pydantic schemas, Alembic migration.
- The 126-test suite, GitHub Actions workflow, Dockerfile / Compose file, seed script, README.
- *TODO(you): anything else.*

## What was verified by running it (not just read)

- Full suite: **126 passed** on in-memory SQLite **and** on PostgreSQL 16; `ruff check` clean.
- Migration: `upgrade → downgrade base → upgrade` on PostgreSQL; a test fails if migration and models drift.
- Live server on PostgreSQL driven with `curl`: register/login, project, member, task create/update,
  filters, summary, and 401 / 403 / 404 / 422 responses.
- Fresh virtualenv from the pinned `requirements-dev.txt`; SQLite zero-setup path; app refuses to start in
  `production` with a placeholder secret.
- Not run in the hardening environment: the Docker files. *TODO(you): run `docker compose up --build` once and
  note the result here.*
- *TODO(you): list what **you** personally traced or changed (e.g. read `task_service.update` line by line;
  changed X to see which test fails).*

## Where AI-generated code was wrong or insufficient

The scaffold shipped with a green test-suite and a README that described behaviour that did not fully work.
Writing stricter tests exposed three real defects:

1. **Unassigning a task did not work.** `PATCH {"assignee_email": null}` returned the *old* assignee, although the
   README promised it unassigns. Cause: the session uses `expire_on_commit=False`, so re-reading the task returned
   the already-loaded, stale relationship. Fix: `populate_existing=True` on the re-fetch, plus a test that
   confirms the change through a second request.
2. **Deleting a project left its tasks behind on SQLite.** The models relied on database-level `ON DELETE CASCADE`,
   which SQLite ignores unless `PRAGMA foreign_keys=ON` is set. The original tests never covered it. Fix: enable
   the pragma on every SQLite connection, plus a cascade test.
3. **Time zones were not handled.** A due date sent as `…+05:30` was stored as local wall-clock time on SQLite,
   so range filters and sorting compared the wrong instants. Fix: normalise all datetimes to UTC on input and
   output; tests cover offsets, naive input, and offset-aware range filters.

Smaller issues of the same kind: a hard-coded database URL in `alembic.ini`; a default JWT secret that would
have been used silently in production; a redundant e-mail index; missing indexes for `GET /projects` and the
`created_at` sort; errors for unknown routes that did not match the documented error shape; unexpected
exceptions that were not logged; and a test-suite that only ever ran against SQLite although the target is
PostgreSQL.

*TODO(you): add one example from your own experience if you have one - it reads more convincingly.*

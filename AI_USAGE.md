# AI Usage Disclosure

I used AI tools heavily on this project. This file records which tools, for what, what I checked myself, and
where the AI output was wrong or incomplete. I remain responsible for all submitted code.

## Tools used

| Tool | Used for |
|---|---|
| ChatGPT | First version of the project: folder structure, models, schemas, routes, first tests and first README. |
| Claude (Anthropic) | Reviewing the project against the assignment brief, fixing the problems it found, writing most of the test suite, CI workflow, Docker files, the seed script and the final README. Also helped me set up and run the project on Windows. |

## Example prompts and use cases

- Uploaded the assignment PDF and the project zip and asked Claude to review the project against the brief.
- "Make best and do all changes, check all things like a senior manager." This led to the hardening pass.
- Asked for step-by-step Windows PowerShell instructions to run the project, and pasted my error messages
  (missing `requirements-dev.txt`, `alembic` and `sqlalchemy` not found, `401 MISSING_TOKEN`, `404 Not Found`)
  to get them explained and fixed.

## What the AI generated

- The layered structure (routers / services / repositories), database models, Pydantic schemas and the
  Alembic migration.
- The 126 automated tests, GitHub Actions workflow, Dockerfile and Docker Compose file, seed script and README.
- The fixes listed in the last section of this file.

## What I verified myself

- Set up the project on my own Windows machine (Python 3.12.10, virtual environment, `pip install`).
- Created the SQLite database with `alembic upgrade head` and loaded demo data with `python -m scripts.seed`.
- Ran `pytest -q` and got **126 passed**.
- Started the server with `uvicorn` and used Swagger UI: logged in as the demo user and received a token,
  authorized with it, and saw `401 MISSING_TOKEN` when I called a protected endpoint without a token.
- Saw a `404` for a project that no longer existed after I deleted data, then reset the database and re-seeded.
- I did not run the Docker Compose setup, because Docker is not installed on my machine. The Docker files are
  provided as an optional extra and I have not tested them myself.

## Where the AI output was wrong or insufficient

The first version had a passing test suite, but stricter tests found real defects, which the AI then fixed:

1. **Unassigning a task did not work.** `PATCH {"assignee_email": null}` returned the old assignee although the
   README said it unassigns. The cause was stale data kept by the database session after commit. Fixed with
   `populate_existing=True` and a test that checks the change in a second request.
2. **Deleting a project left its tasks behind on SQLite.** SQLite ignores foreign-key cascades unless
   `PRAGMA foreign_keys=ON` is set. Fixed by enabling it on every SQLite connection, with a test.
3. **Time zones were handled wrongly.** A due date such as `…+05:30` was stored as local time on SQLite, so date
   filters compared the wrong moments. Fixed by converting every date to UTC on input and output, with tests.

Smaller issues found and fixed: a database URL with credentials hard-coded in `alembic.ini`, a default JWT secret
that could be used silently in production, unknown routes returning a different error format, unexpected errors
not being logged, and tests that only ran on SQLite although the target database is PostgreSQL.

One more example from my own setup: the AI pinned `ruff==0.16.10` in `requirements-dev.txt`, and on my machine
`pip install -r requirements-dev.txt` failed on it, which also stopped every other package from installing. I had
to install the dependencies in separate steps. `ruff` is only a code-style checker and is not needed to run the
app or the tests.

"""Optional demo data: three users, one project, a handful of tasks.

    python -m scripts.seed

Safe to run repeatedly (does nothing if the demo users already exist).
All demo users share the password printed at the end.
"""
from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.enums import Priority, TaskStatus
from app.models import Task
from app.repositories.users import get_user_by_email
from app.services import auth_service, project_service

DEMO_PASSWORD = "Password123!"
USERS = [("Asha Patel", "asha@example.com"), ("Ben Carter", "ben@example.com"), ("Chen Wei", "chen@example.com")]


def main() -> None:
    with SessionLocal() as db:
        if get_user_by_email(db, USERS[0][1]):
            print("Demo data already present - nothing to do.")
            return
        asha, ben, _chen = (
            auth_service.register(db, name=name, email=email, password=DEMO_PASSWORD) for name, email in USERS
        )
        project = project_service.create(db, owner=asha, name="Website Launch", description="Demo project")
        project_service.add_user_by_email(db, project_id=project.id, owner_id=asha.id, email=ben.email)

        now = datetime.now(UTC)
        rows = [
            ("Write launch announcement", Priority.HIGH, TaskStatus.TODO, 3, ben.id, asha.id),
            ("Design landing page", Priority.MEDIUM, TaskStatus.IN_PROGRESS, 7, asha.id, asha.id),
            ("Set up analytics", Priority.LOW, TaskStatus.TODO, 10, None, ben.id),
            ("Register domain", Priority.HIGH, TaskStatus.DONE, -2, asha.id, asha.id),
        ]
        for title, priority, status, due_in_days, assignee_id, creator_id in rows:
            db.add(
                Task(
                    project_id=project.id, creator_id=creator_id, assignee_id=assignee_id, title=title,
                    priority=priority, status=status, due_date=now + timedelta(days=due_in_days),
                    completed_at=now if status == TaskStatus.DONE else None,
                )
            )
        db.commit()
        print(f"Seeded project #{project.id}. Users: {', '.join(e for _, e in USERS)} / password: {DEMO_PASSWORD}")
        print("(chen@example.com is registered but not yet a member - use it to demo 'add member' and 403s.)")


if __name__ == "__main__":
    main()

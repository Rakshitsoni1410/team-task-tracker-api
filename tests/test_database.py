"""Constraints the database itself enforces, independent of application code."""
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.enums import Priority, TaskStatus
from app.models import Project, ProjectMember, Task, User


def _user(email):
    return User(name="U", email=email, password_hash="x")


def _seed(db):
    user = _user("u@example.com")
    db.add(user)
    db.flush()
    project = Project(name="P", owner_id=user.id)
    db.add(project)
    db.flush()
    return user, project


def _task(user, project, **kw):
    base = dict(
        project_id=project.id, creator_id=user.id, title="t", priority=Priority.LOW,
        status=TaskStatus.TODO, due_date=datetime.now(UTC),
    )
    return Task(**{**base, **kw})


def test_email_is_unique_at_database_level(db_session):
    db_session.add(_user("same@example.com"))
    db_session.commit()
    db_session.add(_user("same@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_membership_cannot_be_duplicated(db_session):
    user, project = _seed(db_session)
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id))
    db_session.commit()
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_completed_at_without_done_status_is_rejected_by_the_database(db_session):
    user, project = _seed(db_session)
    db_session.add(_task(user, project, status=TaskStatus.TODO, completed_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_done_task_with_completed_at_is_accepted(db_session):
    user, project = _seed(db_session)
    db_session.add(_task(user, project, status=TaskStatus.DONE, completed_at=datetime.now(UTC)))
    db_session.commit()


def test_task_requires_an_existing_project(db_session):
    user, _ = _seed(db_session)
    db_session.add(Task(project_id=9999, creator_id=user.id, title="t", priority=Priority.LOW,
                        status=TaskStatus.TODO, due_date=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.commit()

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Project, User
from app.repositories.projects import add_member, create_project, get_project, is_member, list_projects_for_user
from app.repositories.users import get_user_by_email


def require_project(db: Session, project_id: int) -> Project:
    project = get_project(db, project_id)
    if project is None:
        raise AppError(404, "PROJECT_NOT_FOUND", "Project not found")
    return project


def require_member(db: Session, project_id: int, user_id: int) -> Project:
    project = require_project(db, project_id)
    if not is_member(db, project_id, user_id):
        raise AppError(403, "FORBIDDEN", "You are not a member of this project")
    return project


def require_owner(db: Session, project_id: int, user_id: int) -> Project:
    project = require_project(db, project_id)
    if project.owner_id != user_id:
        raise AppError(403, "FORBIDDEN", "Only the project owner can perform this action")
    return project


def create(db: Session, *, owner: User, name: str, description: str | None) -> Project:
    project = create_project(db, name=name, description=description, owner=owner)
    db.commit()
    return require_project(db, project.id)


def list_for_user(db: Session, user_id: int) -> list[Project]:
    return list_projects_for_user(db, user_id)


def add_user_by_email(db: Session, *, project_id: int, owner_id: int, email: str) -> Project:
    require_owner(db, project_id, owner_id)
    user = get_user_by_email(db, email)
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "No registered user exists with that email")
    if is_member(db, project_id, user.id):
        raise AppError(409, "ALREADY_MEMBER", "User is already a project member")
    try:
        add_member(db, project_id, user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "ALREADY_MEMBER", "User is already a project member") from None
    return require_project(db, project_id)


def delete(db: Session, *, project_id: int, owner_id: int) -> None:
    project = require_owner(db, project_id, owner_id)
    db.delete(project)
    db.commit()

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Project, ProjectMember, User


def create_project(db: Session, *, name: str, description: str | None, owner: User) -> Project:
    project = Project(name=name, description=description, owner_id=owner.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=owner.id))
    db.flush()
    return project


def get_project(db: Session, project_id: int) -> Project | None:
    return db.scalar(
        select(Project)
        .options(
            selectinload(Project.owner),
            selectinload(Project.memberships).selectinload(ProjectMember.user),
        )
        .where(Project.id == project_id)
    )


def list_projects_for_user(db: Session, user_id: int) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .options(selectinload(Project.owner))
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.created_at.desc())
        ).all()
    )


def is_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        is not None
    )


def add_member(db: Session, project_id: int, user_id: int) -> ProjectMember:
    membership = ProjectMember(project_id=project_id, user_id=user_id)
    db.add(membership)
    db.flush()
    return membership

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.enums import Priority, TaskStatus
from app.models import Project, User
from app.schemas import (
    PROTECTED_ERRORS,
    AddMemberRequest,
    PaginatedTasks,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    SortField,
    SortOrder,
    TaskCreate,
    TaskOut,
    TaskSummary,
    UserBrief,
)
from app.services import project_service, task_service

router = APIRouter(prefix="/projects", tags=["Projects"], responses=PROTECTED_ERRORS)


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        owner=UserBrief.model_validate(project.owner),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def project_detail(project: Project) -> ProjectDetail:
    base = project_out(project)
    return ProjectDetail(
        **base.model_dump(),
        members=[UserBrief.model_validate(m.user) for m in project.memberships],
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return project_detail(
        project_service.create(db, owner=current_user, name=payload.name, description=payload.description)
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [project_out(p) for p in project_service.list_for_user(db, current_user.id)]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return project_detail(project_service.require_member(db, project_id, current_user.id))


@router.post("/{project_id}/members", response_model=ProjectDetail, summary="Add a member by e-mail (owner only)")
def add_member(
    project_id: int,
    payload: AddMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = project_service.add_user_by_email(
        db, project_id=project_id, owner_id=current_user.id, email=str(payload.email)
    )
    return project_detail(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_service.delete(db, project_id=project_id, owner_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.create(db, project_id=project_id, actor=current_user, payload=payload)


@router.get(
    "/{project_id}/tasks",
    response_model=PaginatedTasks,
    summary="List tasks (paginated, filtered, sorted)",
)
def list_tasks(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50, description="Default 10, maximum 50"),
    task_status: TaskStatus | None = Query(None, alias="status"),
    priority: Priority | None = None,
    assignee: str | None = Query(None, description="Assignee e-mail (case-insensitive)"),
    due_from: datetime | None = Query(None, description="Inclusive. ISO-8601; URL-encode '+' as %2B"),
    due_to: datetime | None = Query(None, description="Inclusive. ISO-8601; URL-encode '+' as %2B"),
    sort_by: SortField = "created_at",
    sort_order: SortOrder = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total, pages = task_service.list_for_project(
        db,
        project_id=project_id,
        actor_id=current_user.id,
        page=page,
        page_size=page_size,
        status=task_status,
        priority=priority,
        assignee_email=assignee,
        due_from=due_from,
        due_to=due_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedTasks(items=items, page=page, page_size=page_size, total=total, pages=pages)


@router.get("/{project_id}/summary", response_model=TaskSummary)
def project_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.summary(db, project_id=project_id, actor_id=current_user.id)

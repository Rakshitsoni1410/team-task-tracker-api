from datetime import UTC, datetime
from math import ceil

from sqlalchemy.orm import Session

from app.enums import Priority, TaskStatus
from app.errors import AppError
from app.models import Task, User
from app.repositories import tasks as task_repo
from app.repositories.projects import is_member
from app.repositories.users import get_user_by_email
from app.schemas import TaskCreate, TaskUpdate
from app.services.project_service import require_member, require_project
from app.timeutils import ensure_utc


def _member_assignee_id(db: Session, *, project_id: int, email: str | None) -> int | None:
    if email is None:
        return None
    user = get_user_by_email(db, email)
    if user is None or not is_member(db, project_id, user.id):
        raise AppError(400, "INVALID_ASSIGNEE", "Assignee must be a registered member of this project")
    return user.id


def create(db: Session, *, project_id: int, actor: User, payload: TaskCreate) -> Task:
    require_member(db, project_id, actor.id)
    assignee_id = _member_assignee_id(db, project_id=project_id, email=payload.assignee_email)
    task = task_repo.create_task(
        db,
        project_id=project_id,
        creator_id=actor.id,
        assignee_id=assignee_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status=TaskStatus.TODO,
        due_date=payload.due_date,
    )
    db.commit()
    return task_repo.get_task(db, task.id)  # type: ignore[return-value]


def get_authorized(db: Session, *, task_id: int, actor_id: int) -> Task:
    task = task_repo.get_task(db, task_id)
    if task is None:
        raise AppError(404, "TASK_NOT_FOUND", "Task not found")
    if not is_member(db, task.project_id, actor_id):
        raise AppError(403, "FORBIDDEN", "You are not a member of this project")
    return task


def update(db: Session, *, task_id: int, actor: User, payload: TaskUpdate) -> Task:
    """Partially update a task.

    Only fields the client actually sent (``model_fields_set``) are touched, which is what
    lets ``{"assignee_email": null}`` mean "unassign" while an omitted key means "leave as is".
    """
    task = get_authorized(db, task_id=task_id, actor_id=actor.id)
    fields = payload.model_fields_set

    if "title" in fields:
        if payload.title is None:
            raise AppError(422, "VALIDATION_ERROR", "title cannot be null")
        task.title = payload.title
    if "description" in fields:
        task.description = payload.description
    if "priority" in fields:
        if payload.priority is None:
            raise AppError(422, "VALIDATION_ERROR", "priority cannot be null")
        task.priority = payload.priority
    if "due_date" in fields:
        if payload.due_date is None:
            raise AppError(422, "VALIDATION_ERROR", "due_date cannot be null")
        task.due_date = payload.due_date
    if "assignee_email" in fields:
        task.assignee_id = _member_assignee_id(
            db, project_id=task.project_id, email=payload.assignee_email
        )
    if "status" in fields:
        if payload.status is None:
            raise AppError(422, "VALIDATION_ERROR", "status cannot be null")
        previous = task.status
        task.status = payload.status
        if payload.status == TaskStatus.DONE and previous != TaskStatus.DONE:
            task.completed_at = datetime.now(UTC)  # first transition into DONE
        elif payload.status != TaskStatus.DONE:
            task.completed_at = None  # reopened (or never done): keep the invariant
        # DONE -> DONE leaves the original completed_at untouched

    db.commit()
    return task_repo.get_task(db, task.id)  # type: ignore[return-value]


def delete(db: Session, *, task_id: int, actor: User) -> None:
    task = get_authorized(db, task_id=task_id, actor_id=actor.id)
    project = require_project(db, task.project_id)
    if actor.id not in (project.owner_id, task.creator_id):
        raise AppError(403, "FORBIDDEN", "Only the project owner or task creator can delete this task")
    db.delete(task)
    db.commit()


def list_for_project(
    db: Session,
    *,
    project_id: int,
    actor_id: int,
    page: int,
    page_size: int,
    status: TaskStatus | None,
    priority: Priority | None,
    assignee_email: str | None,
    due_from,
    due_to,
    sort_by: str,
    sort_order: str,
):
    require_member(db, project_id, actor_id)
    due_from, due_to = ensure_utc(due_from), ensure_utc(due_to)
    if due_from and due_to and due_from > due_to:
        raise AppError(400, "INVALID_DATE_RANGE", "due_from must be earlier than or equal to due_to")
    assignee_id = None
    if assignee_email:
        user = get_user_by_email(db, assignee_email)
        if user is None or not is_member(db, project_id, user.id):
            return [], 0, 0
        assignee_id = user.id
    items, total = task_repo.list_tasks(
        db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        due_from=due_from,
        due_to=due_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pages = ceil(total / page_size) if total else 0
    return items, total, pages


def summary(db: Session, *, project_id: int, actor_id: int):
    require_member(db, project_id, actor_id)
    total, status_rows, priority_rows = task_repo.summary_counts(db, project_id)
    by_status = {value: 0 for value in TaskStatus}
    by_priority = {value: 0 for value in Priority}
    for status, count in status_rows:
        by_status[status] = count
    for priority, count in priority_rows:
        by_priority[priority] = count
    return {"total": total, "by_status": by_status, "by_priority": by_priority}

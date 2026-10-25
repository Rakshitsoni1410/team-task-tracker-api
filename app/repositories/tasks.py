from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.enums import Priority, TaskStatus
from app.models import Task


def get_task(db: Session, task_id: int) -> Task | None:
    return db.scalar(
        select(Task)
        .options(selectinload(Task.creator), selectinload(Task.assignee))
        .where(Task.id == task_id)
        # Sessions use expire_on_commit=False, so without this a re-fetch after an update
        # would hand back the stale, already-loaded relationships (e.g. the old assignee).
        .execution_options(populate_existing=True)
    )


def create_task(db: Session, **kwargs) -> Task:
    task = Task(**kwargs)
    db.add(task)
    db.flush()
    db.refresh(task)
    return get_task(db, task.id)  # type: ignore[return-value]


def list_tasks(
    db: Session,
    *,
    project_id: int,
    page: int,
    page_size: int,
    status: TaskStatus | None,
    priority: Priority | None,
    assignee_id: int | None,
    due_from: datetime | None,
    due_to: datetime | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[Task], int]:
    conditions = [Task.project_id == project_id]
    if status is not None:
        conditions.append(Task.status == status)
    if priority is not None:
        conditions.append(Task.priority == priority)
    if assignee_id is not None:
        conditions.append(Task.assignee_id == assignee_id)
    if due_from is not None:
        conditions.append(Task.due_date >= due_from)
    if due_to is not None:
        conditions.append(Task.due_date <= due_to)

    sort_column = Task.created_at if sort_by == "created_at" else Task.due_date
    direction = asc if sort_order == "asc" else desc
    # id is a deterministic tie-breaker in the same direction, so pages never overlap or skip rows.
    order_clauses = (direction(sort_column), direction(Task.id))

    total = db.scalar(select(func.count(Task.id)).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Task)
            .options(selectinload(Task.creator), selectinload(Task.assignee))
            .where(*conditions)
            .order_by(*order_clauses)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def summary_counts(db: Session, project_id: int):
    total = db.scalar(select(func.count(Task.id)).where(Task.project_id == project_id)) or 0
    status_rows = db.execute(
        select(Task.status, func.count(Task.id)).where(Task.project_id == project_id).group_by(Task.status)
    ).all()
    priority_rows = db.execute(
        select(Task.priority, func.count(Task.id)).where(Task.project_id == project_id).group_by(Task.priority)
    ).all()
    return total, status_rows, priority_rows

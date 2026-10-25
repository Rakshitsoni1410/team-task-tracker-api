from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import Priority, TaskStatus
from app.timeutils import ensure_utc

# Every datetime that enters or leaves the API is normalised to timezone-aware UTC.
UTCDatetime = Annotated[datetime, AfterValidator(ensure_utc)]


class StrictRequest(BaseModel):
    """Request bodies reject unknown fields so typos fail loudly instead of being ignored."""

    model_config = ConfigDict(extra="forbid")


def _strip_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} cannot be blank")
    return cleaned


# ---------------------------------------------------------------- errors (docs)
class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


PROTECTED_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token"},
    403: {"model": ErrorResponse, "description": "Authenticated but not allowed"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


# ---------------------------------------------------------------------- users
class UserBrief(BaseModel):
    id: int
    name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _strip_required(value, "name")


class LoginRequest(StrictRequest):
    email: EmailStr
    password: str = Field(max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief


# ------------------------------------------------------------------- projects
class ProjectCreate(StrictRequest):
    name: str = Field(max_length=160)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _strip_required(value, "project name")


class AddMemberRequest(StrictRequest):
    email: EmailStr


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    owner: UserBrief
    created_at: UTCDatetime
    updated_at: UTCDatetime
    model_config = ConfigDict(from_attributes=True)


class ProjectDetail(ProjectOut):
    members: list[UserBrief]


# ---------------------------------------------------------------------- tasks
class TaskCreate(StrictRequest):
    title: str = Field(max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    priority: Priority
    due_date: UTCDatetime
    assignee_email: EmailStr | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _strip_required(value, "task title")


class TaskUpdate(StrictRequest):
    """PATCH body: only fields that are present are changed."""

    title: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    priority: Priority | None = None
    status: TaskStatus | None = None
    due_date: UTCDatetime | None = None
    assignee_email: EmailStr | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _strip_required(value, "task title")


class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str | None
    priority: Priority
    status: TaskStatus
    due_date: UTCDatetime
    completed_at: UTCDatetime | None
    creator: UserBrief
    assignee: UserBrief | None
    created_at: UTCDatetime
    updated_at: UTCDatetime
    model_config = ConfigDict(from_attributes=True)


class PaginatedTasks(BaseModel):
    items: list[TaskOut]
    page: int
    page_size: int
    total: int
    pages: int


class TaskSummary(BaseModel):
    total: int
    by_status: dict[TaskStatus, int]
    by_priority: dict[Priority, int]


SortField = Literal["created_at", "due_date"]
SortOrder = Literal["asc", "desc"]

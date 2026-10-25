from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.repositories.users import get_user_by_id
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise AppError(401, "MISSING_TOKEN", "Authentication token is required")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError(401, "INVALID_TOKEN", "Authentication token is invalid or expired")
    user = get_user_by_id(db, user_id)
    if user is None:
        raise AppError(401, "INVALID_TOKEN", "Authentication token is invalid")
    return user

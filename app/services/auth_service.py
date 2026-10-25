from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.repositories.users import create_user, get_user_by_email
from app.security import burn_password_check, create_access_token, hash_password, verify_password


def register(db: Session, *, name: str, email: str, password: str):
    normalized = email.strip().lower()
    if get_user_by_email(db, normalized):
        raise AppError(409, "DUPLICATE_EMAIL", "A user with this email already exists")
    user = create_user(db, name=name, email=normalized, password_hash=hash_password(password))
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent registrations can both pass the check above; the unique
        # index is the real guarantee.
        db.rollback()
        raise AppError(409, "DUPLICATE_EMAIL", "A user with this email already exists") from None
    db.refresh(user)
    return user


def login(db: Session, *, email: str, password: str):
    user = get_user_by_email(db, email)
    if user is None:
        burn_password_check(password)
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    if not verify_password(password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    return user, create_access_token(user.id)

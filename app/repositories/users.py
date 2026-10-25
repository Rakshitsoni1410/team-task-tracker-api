from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(db: Session, *, name: str, email: str, password_hash: str) -> User:
    user = User(name=name, email=email.strip().lower(), password_hash=password_hash)
    db.add(user)
    db.flush()
    return user

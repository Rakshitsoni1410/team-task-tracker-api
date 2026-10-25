from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AuthResponse, ErrorResponse, LoginRequest, RegisterRequest, UserBrief
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserBrief,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "E-mail already registered"},
               422: {"model": ErrorResponse, "description": "Validation error"}},
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register(db, name=payload.name, email=str(payload.email), password=payload.password)


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={401: {"model": ErrorResponse, "description": "Invalid credentials"},
               422: {"model": ErrorResponse, "description": "Validation error"}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, token = auth_service.login(db, email=str(payload.email), password=payload.password)
    return AuthResponse(access_token=token, user=UserBrief.model_validate(user))

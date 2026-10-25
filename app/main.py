import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.routers import auth, projects, tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "REST API for projects, project membership and team tasks.\n\n"
        "**Authenticate in Swagger:** call `POST /auth/login`, copy `access_token`, click "
        "**Authorize** and paste the token (no `Bearer ` prefix needed).\n\n"
        "All errors share one shape: `{\"error\": {\"code\": \"...\", \"message\": \"...\"}}`."
    ),
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

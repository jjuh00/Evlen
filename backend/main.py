"""FastAPI entry point. Wires together the lifespan hooks, static file mounts, Jinja2 templates, and all routers."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from database import connect_database, close_database
from config import settings
from models.user import UserPublic
from routers.auth import router as auth_router
from utils.authentication import get_optional_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app startup and shutdown.
    """
    await connect_database()
    yield
    await close_database()

# FastAPI instance
app = FastAPI(
    title="Evlen Backend",
    description="Event management web app",
    lifespan=lifespan
)

# Static files. This mount server files from the /frontend/static directory at the /static URL path.
# Must be registered before any routes that need to serve static files. The directory path is absolute to ensure it works correctly in Docker.
app.mount("/static", StaticFiles(directory="/frontend/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="/frontend/templates")

# Routers
# Authentication routes (register, login, logout)
app.include_router(auth_router)

# Public routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: UserPublic | None = Depends(get_optional_user)):
    """
    Homepage.

    Params:
        request: Passed to Jinja2 as required by the TemplateResponse.
        current_user: None for anonymous user, or a UserPublic object for an authenticated user. Injected by the get_optional_user dependency.

    Returns:
        Rendered index.html template with the app name passed as context.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": "Evlen", "current_user": current_user}
    )

@app.get("/health")
async def health():
    """
    Lightweight healt-check endpoint.
    
    Returns:
        dict: Simple status message and current environment for monitoring and debugging.
    """
    return {"status": "ok", "environment": settings.environment}
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import Optional

from database import connect_database, close_database
from scheduler import start_scheduler, stop_scheduler
from config import settings
from models.user import UserPublic
from routers.auth import router as auth_router
from routers.events import router as events_router
from routers.pages import router as pages_router
from routers.rsvp import router as rsvp_router
from utils.authentication import get_optional_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app startup and shutdown.

    On startup, established the MongoDB conenction, creates database indexes, then starts
    the background scheduler for cleaning up past events. 
    On shutdown, it gracefully stops the scheduler and closes the database connection.
    """
    await connect_database()

    # Ensure indexes are created before handling any requests
    from database import get_database
    db = get_database()
    await db["events"].create_index([("date", 1)])
    await db["events"].create_index([("owner_id", 1)])
    await db["events"].create_index([("tags", 1)])
    await db["events"].create_index([("is_deleted", 1)])
    await db["users"].create_index("email", unique=True)
    logger.info("[Database] Indexes ensured")

    # Start the background scheduler
    start_scheduler()

    yield

    # Shutdown: Stop the scheduler and close the database connection
    stop_scheduler()
    await close_database()

# FastAPI instance
app = FastAPI(
    title="Evlen Backend",
    description="Event management web app",
    lifespan=lifespan,
    # Disable the auto-generated docs
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc"
)

# Static files. This mount server files from the /frontend/static directory at the /static URL path.
# Must be registered before any routes that need to serve static files. The directory path is absolute to ensure it works correctly in Docker.
app.mount("/static", StaticFiles(directory="/frontend/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="/frontend/templates")

# Routers
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(pages_router)
app.include_router(rsvp_router)

# Top-level public routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: Optional[UserPublic] = Depends(get_optional_user)):
    """
    Homepage.

    Params:
        request: Passed to Jinja2 as required by the TemplateResponse.
        current_user: The currently authenticated user, if any.

    Returns:
        Rendered index.html template.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "current_user": current_user}
    )

@app.get("/health")
async def health():
    """
    Lightweight health-check endpoint.
    
    Returns:
        dict: {"status": "ok", "environment": "<app_env>"}
    """
    return {"status": "ok", "environment": settings.environment}
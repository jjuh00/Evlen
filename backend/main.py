from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import connect_database, close_database
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_database()
    yield
    await close_database()

app = FastAPI(
    title="Evlen Backend",
    description="Event management web app",
    lifespan=lifespan
)

# Static files
app.mount("/static", StaticFiles(directory="/frontend/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="/frontend/templates")

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": "Evlen"},
    )

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
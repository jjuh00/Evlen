from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import Optional

from utils.authentication import get_current_user, get_optional_user
from database import get_database
from models.user import UserPublic
from utils.helpers import document_to_event, validate_object_id

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="/frontend/templates")

# GET /dashboard
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic = Depends(get_current_user)   
):
    """
    Render the dashboard page for the authenticated user.

    Shows the user's own events (both upcoming and soft-deleted),
    and exposes the event creation form. Requires authentication (raises 401 if not authenticated
    or JWT cookie is missing/invalid).

    Params:
        request: FastAPI Request object.
        db: Motor database instance.
        current_user: The currently authenticated user.

    Returns:
        TemplateResponse: The rendered dashboard.html.
    """
    now = datetime.now(timezone.utc)

    # Upcoming events owner by this user (not deleted)
    my_events_cursor = db["events"].find(
        {"owner_id": current_user.id, "is_deleted": False, "date": {"$gte": now}},
        sort=[("date", 1)]
    )
    my_events = [document_to_event(doc) async for doc in my_events_cursor]

    # Past events owned by this user (soft-deleted by the scheduler)
    past_cursor = db["events"].find(
        {"owner_id": current_user.id, "is_deleted": True}, sort=[("date", -1)], limit=10
    )
    past_events = [document_to_event(doc) async for doc in past_cursor]

    # Render the dashboard template with the user's events
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "my_events": my_events,
            "past_events": past_events,
            "event": None, # Don't include an event when rendering the dashboard
            "is_edit": False
        }
    )

# GET /events/new
@router.get("/events/new", response_class=HTMLResponse)
async def new_event_form(request: Request, current_user: UserPublic = Depends(get_current_user)):
    """
    Render the event creation form.

    The route is used when the user navigates to the event creation page.

    Params:
        request: FastAPI Request object.
        current_user: The currently authenticated user (raises 401 if not authenticated or JWT cookie is missing/invalid).

    Returns:
        TemplateResponse: The rendered event_new.html template.
    """
    return templates.TemplateResponse(
        "event_new.html",
        {"request": request, "current_user": current_user, "event": None}
    )

# GET /events/{event_id}
@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail_page(
    event_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: Optional[UserPublic] = Depends(get_optional_user)
):
    # Validate the event_id and fetch the event document
    _oid = validate_object_id(event_id)
    doc = await db["events"].find_one({"_id": _oid, "is_deleted": False})

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found or has been deleted")

    # If the event is private, check if the user is authenticated and is either the owner or an admin
    if doc.get("is_private"):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This event is private"
            )
        is_owner = str(doc["owner_id"]) == str(current_user.id)
        is_admin = current_user.role == "admin"
        if not (is_owner or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This event is private"
            )

    # Convert the MongoDB document to the EventPublic model for rendering
    doc["id"] = str(doc["_id"])
    attendees = doc.get("attendees", [])
    doc["attendee_count"] = len(attendees)
    capacity = doc.get("capacity")
    fill_pct = min(int(len(attendees) / capacity * 100), 100) if capacity else 0

    # Determine if the current user is attending, is the owner
    # or is an admin for conditional rendering in the template
    is_attending = bool(current_user and str(current_user.id) in attendees)
    is_owner = bool(current_user and str(doc["owner_id"]) == str(current_user.id))
    is_admin = bool(current_user and current_user.role == "admin")

    return templates.TemplateResponse(
        "event_page.html",
        {
            "request": request,
            "event": document_to_event(doc),
            "current_user": current_user,
            "fill_pct": fill_pct,
            "is_attending": is_attending,
            "is_owner": is_owner,
            "is_admin": is_admin
        }
    )
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone

from utils.authentication import get_current_user
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
            "past_events": past_events
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
        TemplateResponse: The rendered event_form partial.
    """
    return templates.TemplateResponse(
        "event_form.html",
        {"request": request, "current_user": current_user, "event": None}
    )

# GET /events/{event_id}
@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_card(
    event_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic | None = Depends(get_current_user)
):
    """
    Render the full detail page for a single event. Private events will only be shown if the user is the owner or an admin.

    Params:
        event_id: The ID of the event to display.
        request: FastAPI Request object.
        db: Motor database instance.
        current_user: The currently authenticated user, or None for anonymous users.

    Returns:
        TemplateResponse: Rendered event_page.html

    Raises:
        HTTPException: 404 if event doesn't exist or is soft-deleted.
        HTTPException: 403 if the event is private and the user isn't the owner or an admin.
    """
    # Validate event_id and fetch the event document
    oid = validate_object_id(event_id)
    event_doc = await db["events"].find_one({"_id": oid, "is_deleted": False})
    if not event_doc:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = document_to_event(event_doc)

    # Enforce private visibility
    if event.is_private:
        if not current_user:
            return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
        if current_user.id != event.owner_id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You don't have permission to view this event")
    
    # Determine if the current user is the owner or an admin or an attendee
    is_owner = current_user is not None and (
        current_user.id == event.owner_id or current_user.role == "admin"
    )
    is_attending = current_user is not None and current_user.id in event.attendees

    # Render the event detail page with the event data and user permissions
    return templates.TemplateResponse(
        "event_page.html",
        {
            "request": request,
            "current_user": current_user,
            "event": event,
            "is_owner": is_owner,
            "is_attending": is_attending
        }
    )
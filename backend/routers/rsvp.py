from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from typing import Any
import json
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone

from database import get_database
from models.event import EventPublic
from models.user import UserPublic
from utils.authentication import get_current_user
from utils.helpers import validate_object_id, set_flash_cookie, document_to_event

router = APIRouter(prefix="/events", tags=["rsvp"])
templates = Jinja2Templates(directory="/frontend/templates")

# Private helpers
def _trigger_toast(message: str, toast_type: str = "info") -> str:
    """
    Serialize a showToast payload for HX-Trigger response header.

    HTMX fires a custom "showToast" DOM event on the body elemet after receiving this header.
    toast.js listens for that event and calls showToast().

    Params:
        message: The human-readable message to show in the toast notification.
        toast_type: The type of the toast (e.g. "success", "info", "warning", "error"), which controls its styling.

    Returns:
        str: A JSON string suitable for the HX-Trigger header.
    """
    payload: dict[str, Any] = {"showToast": {"message": message, "type": toast_type}}
    return json.dumps(payload)

def _render_rsvp_section(request: Request, event: EventPublic, current_user: UserPublic, is_attending: bool) -> str:
    """
    Render the rsvp_button.html partial and wrap it in the #rsvp-section div.

    The wrapper is needed because the RSVP buttons use hx-swa="outerHTML" targeting #rsvp-section.
    HTMX replaces the entire div, so the response must include it.

    Params:
        request: FastAPI Request object.
        event: The current EventPublic instance.
        current_user: The currently authenticated user.
        is_attending: Whether the current user is attending the event.

    Returns:
        str: The rendered HTML for the RSVP section, including the wrapper div.
    """
    inner = templates.get_template("partials/rsvp_button.html").render(
        {
            "request": request,
            "event": event,
            "current_user": current_user,
            "is_attending": is_attending
        }
    )
    return f'<div id="rsvp-section">{inner}</div>'

# POST /events/{event_id}/rsvp
@router.post("/{event_id}/rsvp", response_class=HTMLResponse)
async def rsvp_add(
    event_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Add authenticated user to event's attendee list (RSVP).

    Enforces the event's capacity limit and prevents RSVPS for past or already-attended events.
    Returns the updated rsvp_button.html partial so HTMX can swap it in-place, and
    sets HTMX-Trigger to fire a toast notification without a page reload.

    Params:
        event_id: The ID of the event to RSVP to.
        request: FastAPI Request object.
        db: Motor database instance.
        current_user: The currently authenticated user.

    Returns:
        HTMLResponse: The rendered #rsvp-section partial with an HX-Trigger toast header.

    Raises:
        HTTPException: 404 if event doesn't exist.
    """
    # Validate event_id and fetch the event document
    oid = validate_object_id(event_id)
    event_doc = await db["events"].find_one({"_id": oid, "is_deleted": False})
    if not event_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    # Don't allow RSVPs to past events
    event_date = event_doc["date"]
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)

    # Check if user is already attending or if event is at capacity
    attendees = event_doc.get("attendees", [])
    capacity = event_doc.get("capacity")

    toast_message = ""
    toast_type = "info"

    # Determine the appropriate toast message and type based on RSVP outcome
    if event_date < datetime.now(timezone.utc):
        toast_message, toast_type = "This event has already occurred", "warning"
    elif current_user.id in attendees:
        toast_message, toast_type = "You're already signed up for this event", "info"
    elif capacity is not None and len(attendees) >= capacity:
        toast_message, toast_type = "This event is already at full capacity", "error"
    else:
        # Successful RSVP
        await db["events"].update_one(
            {"_id": oid}, {"$addToSet": {"attendees": current_user.id}}
        )
        event_doc = await db["events"].find_one({"_id": oid})  # Reload to get updated attendees
        toast_message, toast_type = "You've successfully signed up for this event!", "success"

    # Render the updated RSVP section partial with fresh event data
    event = document_to_event(event_doc)
    is_attending = current_user.id in event.attendees

    html = _render_rsvp_section(request, event, current_user, is_attending)
    response = HTMLResponse(content=html, status_code=status.HTTP_200_OK)
    response.headers["HX-Trigger"] = _trigger_toast(toast_message, toast_type)
    return response

# DELETE /events/{event_id}/rsvp
@router.delete("/{event_id}/rsvp", response_class=HTMLResponse)
async def rsvp_remove(
    event_id: str,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Remove the authenticated user from the event's attendee list (cancel RSVP).

    Params:
        event_id: The ID of the event to cancel RSVP for.
        request: FastAPI Request object.
        db: Motor database instance.
        current_user: The currently authenticated user.

    Returns:
        HTMLResponse: The rendered #rsvp-section partial with an HX-Trigger toast header.

    Raises:
        HTTPException: 404 if event doesn't exist.
    """
    # Validate event_id and fetch the event document
    oid = validate_object_id(event_id)
    event_doc = await db["events"].find_one({"_id": oid, "is_deleted": False})
    if not event_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    # Check if the user is currently attending
    attendees = event_doc.get("attendees", [])
   
    if current_user.id not in attendees:
        toast_message, toast_type = "You're not currently signed up for this event", "info"
    else:
        # Successful RSVP cancellation
        await db["events"].update_one(
            {"_id": oid}, {"$pull": {"attendees": current_user.id}}
        )
        event_doc = await db["events"].find_one({"_id": oid})  # Reload to get updated attendees
        toast_message, toast_type = "You've successfully canceled your RSVP for this event!", "success"

    # Render the updated RSVP section partial with fresh event data
    event = document_to_event(event_doc)
    is_attending = current_user.id in event.attendees
    
    html = _render_rsvp_section(request, event, current_user, is_attending)
    response = HTMLResponse(content=html, status_code=status.HTTP_200_OK)
    response.headers["HX-Trigger"] = _trigger_toast(toast_message, toast_type)
    return response
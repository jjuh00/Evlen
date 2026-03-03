from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone

from database import get_database
from models.user import UserPublic
from utils.authentication import get_current_user
from utils.helpers import validate_object_id, toast_oob_html, document_to_event

router = APIRouter(prefix="/events", tags=["rsvp"])
templates = Jinja2Templates(directory="/frontend/templates")

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

    Enforces the event's capacity limit. Returns the updated rsvp_button partial
    so HTMX can swap it in-place with the existing button, updating the UI to reflect the new RSVP state.

    Params:
        event_id: The ID of the event to RSVP to.
        request: FastAPI Request object.
        db: Motor database instance.
        current_user: The currently authenticated user.

    Returns:
        HTMLResponse: The rendered rsvp_button.html partial plus OOB toast.

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

    if event_date < datetime.now(timezone.utc):
        return HTMLResponse(
            content=toast_oob_html("This event has already occurred", "warning"), status_code=status.HTTP_200_OK
        )
    
    # Check if the user is already attending
    attendees = event_doc.get("attendees", [])

    if current_user.id in attendees:
        return HTMLResponse(
            content=toast_oob_html("You've already signed up for this event", "info"), status_code=status.HTTP_200_OK
        )
    
    # Enforce capacity limit if it exists
    capacity = event_doc.get("capacity")
    if capacity is not None and len(attendees) >= capacity:
        return HTMLResponse(
            content=toast_oob_html("Unfortunately, this event has reached its maximum capacity", "error"), status_code=status.HTTP_200_OK
        )
    
    # Add the user to the attendees list
    await db["events"].update_one(
        {"_id": oid}, {"$addToSet": {"attendees": current_user.id}}
    )

    # Reload the updated event document to pass fresh data to the partial
    updated_doc = await db["events"].find_one({"_id": oid})
    event = document_to_event(updated_doc)

    # Render the updated RSVP button partial with the new event data
    partial_html = templates.get_template("partials/rsvp_button.html").render(
        {
            "request": request,
            "event": event,
            "current_user": current_user,
            "is_attending": True
        }
    )
    toast = toast_oob_html("You've successfully signed up for this event!", "success")

    return HTMLResponse(content=partial_html + toast, status_code=status.HTTP_200_OK)

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
        HTMLResponse: The rendered rsvp_button.html partial plus OOB toast.

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
        return HTMLResponse(
            content=toast_oob_html("You weren't signed up for this event", "info"), status_code=status.HTTP_200_OK
        )
    
    # Remove the user from the attendees list
    await db["events"].update_one(
        {"_id": oid}, {"$pull": {"attendees": current_user.id}}
    )

    # Reload the updated event document to pass fresh data to the partial
    updated_doc = await db["events"].find_one({"_id": oid})
    event = document_to_event(updated_doc)

    partial_html = templates.get_template("partials/rsvp_button.html").render(
        {
            "request": request,
            "event": event,
            "current_user": current_user,
            "is_attending": False
        }
    )
    toast = toast_oob_html("You've successfully canceled your RSVP for this event!", "success")

    return HTMLResponse(content=partial_html + toast, status_code=status.HTTP_200_OK)
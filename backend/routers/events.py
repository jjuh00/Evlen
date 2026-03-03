from fastapi import APIRouter, Request, Depends, status, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone

from models.event import ScheduleSlot
from database import get_database
from utils.authentication import get_optional_user, get_current_user
from models.user import UserPublic
from utils.helpers import (
    filter_events, document_to_event, render_error_html, toast_oob_html, 
    validate_object_id, assert_owner_or_admin
)

router = APIRouter(prefix="/events", tags=["events"])
templates = Jinja2Templates(directory="/frontend/templates")

# Helper
def _parse_schedule(form_data: dict) -> list[ScheduleSlot]:
    """
    Extract ScheduleSlot objects from flat HTML form data.

    The event form submits schedule rows as:
        schedule-time-0, schedule-description-0, schedule_time_1, schedule_description_1, etc.

    Params:
        form_data: The raw form data dictionary from the request.

    Returns:
        list[ScheduleSlot]: A list of ScheduleSlot objects parsed from the form data.
    """
    items: list[ScheduleSlot] = []
    index = 0
    while True:
        time_value = form_data.get(f"schedule-time-{index}", "").strip()
        description_value = form_data.get(f"schedule-description-{index}", "").strip()
        if not time_value and not description_value:
            # No more schedule items found, exit the loop
            break
        if time_value or description_value:
            # Include partial rows so the user gets validation feedback on both fields
            items.append(ScheduleSlot(time=time_value or " ", description=description_value or " "))
        index += 1
    return items

# GET /events
@router.get("", response_class=HTMLResponse)
async def list_events(
    request: Request,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: Optional[UserPublic] = Depends(get_optional_user)
):
    """
    Return an HTML fragment containg event-card partials for all upcoming events.

    This endpoint is the HTMX target for `hx-get="/events"` on the homepage. 
    It streams results in ascedning order by date.

    Params:
        request: The FastAPI Request object.
        tag: Optional query parameter to filter events by a specific tag.
        search: Optional query parameter to perform a text search on event titles and descriptions.
        db: The MongoDB database instance.
        current_user: The currently authenticated user, if any.

    Returns:
        RedirectResponse | TemplateResponse: Redirect to homepage (if not from HTMX) or rendered HTML fragment containing event-card partials for the matching events.
    """
    # A guard: /events is an HTMX fragment endpoint and doesn't make sense to load without HTMX. 
    # If we detect a direct navigation, redirect to the homepage which will then load the events via HTMX as intended
    if not request.headers.get("HX-Request"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    query = filter_events(tag=tag, search=search, include_private=False)

    # Include the current user's own private events if they're logged in
    if current_user:
        private_own = {
            "date": {"$gte": datetime.now(timezone.utc)},
            "is_deleted": False,
            "is_private": True,
            "owner_id": current_user.id
        }
        cursor = db["events"].find({"$or": [query, private_own]}, sort=[("date", 1)])
    else:
        cursor = db["events"].find(query, sort=[("date", 1)])

    # Stream the results
    events = []
    async for doc in cursor:
        events.append(document_to_event(doc))
    
    return templates.TemplateResponse(
        "partials/event_list.html",
        {
            "request": request,
            "events": events,
            "current_user": current_user,
            "active_tag": tag,
            "search": search
        }
    )

# GET /events/tags
@router.get("/tags", response_class=HTMLResponse)
async def list_tags(request: Request, db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Return all distinct tags from upcoming, non-deleted public events.

    Params:
        request: The FastAPI Request object.
        db: The MongoDB database instance.

    Returns:
        TemplateResponse: Tag filter button partials.
    """
    # Collect distinct tags from non-soft-deleted events
    pipeline = [
        {"$match": {"is_deleted": False, "tags": {"$exists": True, "$ne": []}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags"}},
        {"$sort": {"_id": 1}}
    ]

    # Execute the aggregation pipeline to get distinct tags
    cursor = db["events"].aggregate(pipeline)
    tags = [doc["_id"] async for doc in cursor]
    
    return templates.TemplateResponse(
        "partials/tag_filter.html",
        {"request": request, "tags": tags}
    )

# POST /events
@router.post("", response_class=HTMLResponse)
async def create_event(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    date: str = Form(...),
    tags: str = Form(""),
    capacity: Optional[str] = Form(None),
    is_private: Optional[bool] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Create a new event owner by the current user with the provided form data.

    Schedule rows are parsed from dynamically-named form fields:
    schedule-time-0, schedule-description-0, schedule-time-1, schedule-description-1, etc.

    Params:
        request: The FastAPI Request object.
        title: The event title.
        description: The event description.
        date: The event date string.
        tags: Comma-separated tags string.
        capacity: Optional maximum capacity integer.
        is_private: Optional boolean indicating if the event is private.
        db: The MongoDB database instance.
        current_user: The currently authenticated user creating the event.

    Returns:
        HTMLResponse: On success, HX-Redirect header to the new event page plus OOB toast.
                      On failure, an error fragment HTMX can swap into the form to display validation errors.
    """
    # Validate date
    try:
        event_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    except ValueError:
        return render_error_html("Invalid date format, please use the date picker")
    
    if event_date <= datetime.now(timezone.utc):
        return render_error_html("Event date must be in the future")
    
    # Parse optional fields
    parsed_capacity = None
    if capacity and capacity.strip():
        try:
            parsed_capacity = int(capacity.strip())
            if parsed_capacity < 1:
                return render_error_html("Capacity must be a positive integer")
        except ValueError:
            return render_error_html("Capacity must be a valid integer")
        
    parsed_tags = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
    private_flag = is_private == "on"

    # Parse schedule rows from the form data
    form_data = await request.form()
    schedule = _parse_schedule(form_data)

    # Construct the event document
    doc = {
        "title": title.strip(),
        "description": description.strip(),
        "date": event_date,
        "owner_id": current_user.id,
        "owner_display_name": current_user.display_name,
        "schedule": [s.model_dump() for s in schedule],
        "tags": parsed_tags,
        "capacity": parsed_capacity,
        "is_private": private_flag,
        "attendees": [],
        "is_deleted": False,
        "deleted_at": None
    }
    # Insert the new event into the database
    result = await db["events"].insert_one(doc)
    event_id = str(result.inserted_id)

    # Return a response with an HX-Redirect header to the new event page and an OOB toast notification
    response = HTMLResponse(content=toast_oob_html("Event created!", "success"))
    response.headers["HX-Redirect"] = f"/events/{event_id}"
    return response

# PUT /events/{event_id}
@router.put("/{event_id}", response_class=HTMLResponse)
async def update_event(
    event_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    date: str = Form(...),
    tags: str = Form(""),
    capacity: Optional[str] = Form(None),
    is_private: Optional[bool] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Update and existing event. Only the event owner or an admin can update this event.

    Params:
        event_id: The ID of the event to update.
        request: The FastAPI Request object.
        title: The updated event title.
        description: The updated event description.
        date: The updated event date string.
        tags: Updated comma-separated tags string.
        capacity: Optional updated maximum capacity integer.
        is_private: Optional updated boolean indicating if the event is private.
        db: The MongoDB database instance.
        current_user: The currently authenticated user attempting the update.

    Returns:
        HTMLResponse: On success, HX-Redirect header to the event page plus OOB toast.
                      On failure, an error fragment HTMX can swap into the form to display validation errors.
    """
    # Validate event_id
    oid = validate_object_id(event_id)
    
    # Fetch the existing event document to check ownership and existence
    event_doc = await db["events"].find_one({"_id": oid, "is_deleted": False})
    if not event_doc:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Authorization check
    assert_owner_or_admin(event_doc["owner_id"], current_user)

    # Validate date
    try:
        event_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    except ValueError:
        return render_error_html("Invalid date format, please use the date picker")
    
    # Parse optional fields
    parsed_capacity = None
    if capacity and capacity.strip():
        try:
            parsed_capacity = int(capacity.strip())
        except ValueError:
            return render_error_html("Capacity must be a valid integer")
        
    parsed_tags = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
    private_flag = is_private == "on"

    # Parse schedule rows from the form data
    form_data = await request.form()
    schedule = _parse_schedule(form_data)

    # Build the update document
    await db["events"].update_one(
        {"_id": oid},
        {
            "$set": {
                "title": title.strip(),
                "description": description.strip(),
                "date": event_date,
                "schedule": [s.model_dump() for s in schedule],
                "tags": parsed_tags,
                "capacity": parsed_capacity,
                "is_private": private_flag
            }
        }
    )

    # Return a response with an HX-Redirect header to the event page and an OOB toast notification
    response = HTMLResponse(content=toast_oob_html("Event updated!", "success"))
    response.headers["HX-Redirect"] = f"/events/{event_id}"
    return response

# DELETE /events/{event_id}
@router.delete("/{event_id}", response_class=HTMLResponse)
async def delete_event(
    event_id: str, db: AsyncIOMotorDatabase = Depends(get_database), current_user: UserPublic = Depends(get_current_user)
):
    """
    Soft-delete an event by setting `is_deleted` to True and recording the deletion timestamp. 
    Only the event owner or an admin can delete this event.

    The event will be hidden immediately but the document will remain in the database until the background
    scheduler permanently deletes it during its regular cleanup runs.

    Params:
        event_id: The ID of the event to delete.
        db: The MongoDB database instance.
        current_user: The currently authenticated user attempting the deletion.

    Returns:
        HTMLResponse: On success, HX-Redirect header to the homepage plus OOB toast.

    Raises:
        HTTPException: 404 if the event doesn't exist, 403 if the user isn't authorized to delete the event.
    """
    oid = validate_object_id(event_id)

    # Fetch the existing event document to check ownership and existence
    event_doc = await db["events"].find_one({"_id": oid, "is_deleted": False})
    if not event_doc:
        raise HTTPException(status_code=404, detail="Event not found")
    
    assert_owner_or_admin(event_doc["owner_id"], current_user)

    # Soft-delete the event by setting is_deleted to True and recording the deletion timestamp
    await db["events"].update_one(
        {"_id": oid}, {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}}
    )

    # Return a response with an HX-Redirect header to the homepage and an OOB toast notification
    response = HTMLResponse(content=toast_oob_html("Event deleted!", "success"))
    response.headers["HX-Redirect"] = "/dashboard"
    return response
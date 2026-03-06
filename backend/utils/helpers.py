from fastapi.templating import Jinja2Templates
from typing import Optional
from urllib.parse import quote
from fastapi.responses import HTMLResponse
from fastapi import Response, HTTPException, status, Depends
from datetime import datetime, timezone
from bson import ObjectId

from models.event import EventPublic, ScheduleSlot
from models.user import UserPublic
from utils.authentication import get_optional_user

templates = Jinja2Templates(directory="/frontend/templates")

def document_to_event(doc: dict) -> EventPublic:
    """
    Convert a raw MongoDB event document to an EventPublic model instance.

    Params:
        doc: The raw MongoDB document representing an event (with _id as ObjectId).

    Returns:
        EventPublic: Serializable model instance with _id converted to string and all fields properly typed.
    """
    attendees: list[str] = doc.get("attendees", [])
    capacity: Optional[int] = doc.get("capacity")

    return EventPublic(
        id=str(doc["_id"]),
        title=doc["title"],
        description=doc["description"],
        date=doc["date"],
        owner_id=doc["owner_id"],
        owner_display_name=doc.get("owner_display_name", ""),
        schedule=[ScheduleSlot(**slot) for slot in doc.get("schedule", [])],
        tags=doc.get("tags", []),
        capacity=capacity,
        is_private=doc.get("is_private", False),
        attendees=attendees,
        attendee_count=len(attendees),
        is_full=(capacity is not None and len(attendees) >= capacity),
        is_deleted=doc.get("is_deleted", False)
    )

def set_flash_cookie(response: Response, message: str, toast_type: str = "info") -> None:
    """
    Attach short-lived cookie to a response so the next page laod can show a toast.

    HTMX navigates the browser before any OOB content in the response bod can be processed,
    so a flash cookie is used to pass the message across the redirect.

    Params:
        response: The FastAPI Response object to set cookies on.
        message: The human-readable message to show in the toast notification.
        toast_type: The type of the toast (e.g. "success", "info", "warning", "error"), which controls its styling.
    """
    response.set_cookie(
        "flash_message",
        quote(message), # URL-encode so any character is safe in a cookie value
        max_age=30,
        httponly=False, # Allow JS to read this cookie so the client can show the toast message
        samesite="lax",
        path="/"
    )
    response.set_cookie(
        "flash_type",
        toast_type,
        max_age=30,
        httponly=False,
        samesite="lax",
        path="/"
    )

def render_error_html(message: str) -> HTMLResponse:
    """
    Return a 200 HTML fragment containing the given error message.

    Returning 200 allows HTMX to swap the content into the page and display it to the user, 
    since it considers 4xx/5xx responses as errors and won't update the page with the response content.

    Params:
        message: The error message to display to the user.

    Returns:
        HTMLResponse: A small HTML fragment HTMX can inject into the page to show the error message.
    """
    # Escape < and > to prevent HTML injection in the error message
    safe = message.replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        content=f'<p class="error-message fade-in">{safe}</p>',
        status_code=200
    )

def require_authentication_or_redirect(current_user: UserPublic | None = Depends(get_optional_user)) -> None:
    """
    Raise a 401 HTTPException if `current_user` is None, indicating that the user isn't authenticated.

    Use in HTML-serving routes that should be accessible only to authenticated users. 
    When HTMX receives a 401 response, it won't swap the content into the page, allowing you to keep the user on the same page 
    and show an error message instead.

    Params:
        current_user: The current user object, or None if the user isn't authenticated. Resolved from `get_optional_user()`.

    Raises:
        HTTPException: If user isn't authenticated (current_user is None).
    """
    # If the user is not authenticated, raise a 401 error. HTMX won't swap the response content,
    # allowing the client to stay on the same page and show an error message.
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required, please log in"
        )
    
def assert_owner_or_admin(resource_owner_id: str, current_user: UserPublic) -> None:
    """
    Raise a 403 HTTPException if the current user isn't the owner of the resource or an admin.

    Params:
        resource_owner_id: The `owner_id` field of the resource being accessed.
        current_user: Authenticated `UserPublic` object (cannot be None).

    Raises:
        HTTPException: If the user isn't the owner of the resource or an admin.
    """
    # If the user isn't the owner and not an admin, raise a 403 error. 
    # HTMX won't swap the response content, allowing the client to stay on the same page and show an error message.
    if current_user.id != resource_owner_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to perform this action"
        )
    
def filter_events(tag: Optional[str] = None, search: Optional[str] = None, include_private: bool = False) -> dict:
    """
    Build a MongDB filter dict for upcoming, non-deleted events based on the provided query parameters.

    Params:
        tag: Optional tag to filter events by. If provided, only events containing this tag will be included.
        search: Optional search string to filter events by title, description or tags. Case-insensitive partial matches will be included.
        include_private: Whether to include private events in the results. Defaults to False, meaning private events will be excluded.

    Returns:
        dict: A Motor-compatible query filter.
    """
    # Base filter for upcoming, non-deleted events
    now = datetime.now(timezone.utc)
    query = {
        "date": {"$gte": now},
        "is_deleted": False
    }

    if tag:
        query["tags"] = tag

    # If a search string is provided, add a case-insensitive regex filter on the title and description fields
    if search and search.strip():
        regex = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [{"title": regex}, {"description": regex}]

    if not include_private:
        query["is_private"] = False

    return query

def validate_object_id(oid: str) -> ObjectId:
    """
    Parse and validate a MongoDB ObjectId string.

    Params:
        oid: The string to validate and convert to ObjectId.

    Returns:
        ObjectId: The corresponding ObjectId instance if the input is valid.

    Raises:
        HTTPException: If the input string isn't a valid ObjectId.
    """  
    try:
        return ObjectId(oid)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
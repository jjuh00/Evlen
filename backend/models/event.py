from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ScheduleSlot(BaseModel):
    """
    Represents a detailed schedule slot for an event.
    """
    time: str = Field(..., description="Time label")
    description: str = Field(..., description="What happens in this slot")

class EventCreate(BaseModel):
    """
    Data a client submits to create a new event.
    """
    title: str = Field(..., min_length=3, max_length=100, description="Title of the event")
    description: str = Field(..., min_length=5, max_length=1500, description="Detailed description of the event")
    date: datetime = Field(..., description="Event start date and time (in UTC format)")
    schedule: list[ScheduleSlot] = Field(..., default_factory=list, description="Optional detailed schedule for the event")
    tags: list[str] = Field(default_factory=list, description="Event tags for categorization and filtering")
    capacity = Optional[int] = Field(None, gt=0, description="Maximum number of attendees (optional). None means unlimited capacity")
    is_private: bool = Field(False, description="Whether the event is private (private events are only visible to attendees and the owner)")

class EventUpdate(BaseModel):
    """
    Partial update model for events. All fields are optional to allow partial updates.
    """
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, min_length=5, max_length=1500)
    date: Optional[datetime] = None
    schedule: Optional[list[ScheduleSlot]] = None
    tags: Optional[list[str]] = None
    capacity: Optional[int] = Field(None, gt=0)
    is_private: Optional[bool] = None

class EventInDB(BaseModel):
    """
    Full event document as stored in MongoDB.
    Includes all fields including soft-delete state.
    """ 
    id: str = Field(..., description="Stringified MongoDB _id")
    title: str
    description: str
    date: datetime
    owner_id: str = Field(..., description="User ID of the event creator")
    owner_display_name: str = Field(..., description="Display name of the event creator")
    schedule: list[ScheduleSlot] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    capacity: Optional[int] = None
    is_private: bool = False
    attendees: list[str] = Field(default_factory=list, description="List of user IDs attending the event")
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    
class EventPublic(BaseModel):
    """
    Full event representation for public consumption, including all details.
    Derived from the raw MongoDB document structure after casting _id to string.
    """
    id: str
    title: str
    description: str
    date: datetime
    owner_id: str
    owner_display_name: str
    schedule: list[ScheduleSlot] = []
    tags: list[str] = []
    capacity: Optional[int] = None
    is_private: bool = False
    attendees: list[str] = []
    is_deleted: bool = False
    created_at: datetime
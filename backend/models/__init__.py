# Re-export public model classes so routers can import from 'models'
# rather than spelling out the full sub-module path

from .user import UserCreate, UserInDB, UserPublic, UserLogin
from .event import ScheduleSlot, EventCreate, EventUpdate, EventPublic

__all__ = [
    "UserCreate", "UserInDB", "UserPublic", "UserLogin",
    "ScheduleSlot", "EventCreate", "EventUpdate", "EventPublic"
]
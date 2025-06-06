"""
Модуль содержит модели данных для API.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel

from utils.rental_types import RentalTypes


class ApartmentFilter(BaseModel):
    """Model for apartment filter parameters"""

    city: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rooms: Optional[List[int]] = None
    min_square: Optional[float] = None


class UserUpdate(BaseModel):
    """Model for user update request"""

    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    filter_type: Optional[str] = None


class BaseUserFilter(BaseModel):
    """Base model for user filter request"""

    user_id: int
    city: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_square: Optional[float] = None
    rooms: Optional[List[int]] = None


class FullApartmentFilter(BaseUserFilter):
    """Model for full apartment filter"""

    rental_type: Literal[RentalTypes.FULL_APARTMENT] = RentalTypes.FULL_APARTMENT


class RoomSharingFilter(BaseUserFilter):
    """Model for room sharing filter"""

    rental_type: Literal[RentalTypes.ROOM_SHARING] = RentalTypes.ROOM_SHARING
    gender: str
    roommate_preference: str


class UserFilter(BaseUserFilter):
    """Model for user filter request (for backward compatibility)"""

    rental_type: Optional[str] = None
    gender: Optional[str] = None
    roommate_preference: Optional[str] = None

from fastapi import FastAPI, HTTPException
from typing import List, Optional
from database import get_apartments, save_apartment, create_or_update_user, get_active_users, is_user_active
from pydantic import BaseModel

app = FastAPI()

class ApartmentFilter(BaseModel):
    """Model for apartment filter parameters"""
    city: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rooms: Optional[List[int]] = None

class UserUpdate(BaseModel):
    """Model for user update request"""
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True

@app.post("/apartments/filter")
async def filter_apartments(filter_params: ApartmentFilter):
    """
    Filter apartments based on criteria
    
    Args:
        filter_params (ApartmentFilter): Filter parameters
        
    Returns:
        list: Filtered apartments
    """
    try:
        apartments = get_apartments(
            city=filter_params.city,
            min_price=filter_params.min_price,
            max_price=filter_params.max_price,
            rooms=filter_params.rooms
        )
        return [{"url": apt.url, "price": apt.price, "rooms": apt.rooms, "city": apt.city} 
                for apt in apartments]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/users")
async def update_user(user_data: UserUpdate):
    """
    Update user status
    
    Args:
        user_data (UserUpdate): User update data
    """
    try:
        create_or_update_user(
            user_id=user_data.user_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=user_data.is_active
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/active")
async def get_active_user_list():
    """Get list of active users"""
    try:
        return {"users": get_active_users()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/status")
async def get_user_status(user_id: int):
    """Get user status"""
    try:
        return {"is_active": is_user_active(user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
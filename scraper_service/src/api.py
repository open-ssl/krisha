import logging
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Response

from database import ApartmentPhoto, SessionLocal, TelegramApartmentPhoto, create_or_update_user
from database import delete_user_filter as db_delete_user_filter
from database import get_active_users, get_apartments, get_user_filter, is_user_active, save_user_filter
from src.models import ApartmentFilter, FullApartmentFilter, RoomSharingFilter, UserFilter, UserUpdate
from utils.city_mapping import CITY_MAPPING
from utils.rental_types import RentalTypes


app = FastAPI()


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
        # Если указан город, преобразуем его название из русского в английское для поиска
        city = filter_params.city
        if city:
            if city.lower() in CITY_MAPPING:
                city = CITY_MAPPING[city.lower()]

        apartments = get_apartments(
            city=city,
            rooms=filter_params.rooms,
            min_price=filter_params.min_price,
            max_price=filter_params.max_price,
            min_square=filter_params.min_square,
        )

        # Преобразуем объекты в словари с нужными полями
        return [
            {
                "id": apt["id"],
                "url": apt["url"],
                "price": apt["price"],
                "rooms": apt["rooms"],
                "square": apt["square"],
                "city": apt["city"],
                "district": apt.get("district"),
                "street": apt.get("street"),
                "complex_name": apt.get("complex_name"),
            }
            for apt in apartments
        ]
    except Exception as e:
        logging.error(f"Error filtering apartments: {e}")
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
            is_active=user_data.is_active,
            filter_type=user_data.filter_type if user_data.is_active else None,
        )

        if not user_data.is_active:
            db_delete_user_filter(user_data.user_id)
            logging.debug(f"Deleted all filters for user_id {user_data.user_id}")

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


@app.post("/users/filters")
async def set_user_filter(filter_data: UserFilter):
    """Set user filter (backward compatibility)"""
    try:
        # Обновляем тип фильтра пользователя
        create_or_update_user(
            user_id=filter_data.user_id,
            filter_type=filter_data.rental_type,
        )

        # Сохраняем фильтр
        save_user_filter(
            user_id=filter_data.user_id,
            city=filter_data.city,
            min_price=filter_data.min_price,
            max_price=filter_data.max_price,
            min_square=filter_data.min_square,
            rooms=filter_data.rooms,
            rental_type=filter_data.rental_type,
            gender=filter_data.gender,
            roommate_preference=filter_data.roommate_preference,
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/users/filters/full-apartment")
async def set_full_apartment_filter(filter_data: FullApartmentFilter):
    """Set filter for full apartment"""
    try:
        # Обновляем тип фильтра пользователя
        create_or_update_user(
            user_id=filter_data.user_id,
            filter_type=RentalTypes.FULL_APARTMENT,
        )

        # Сохраняем фильтр
        save_user_filter(
            user_id=filter_data.user_id,
            city=filter_data.city,
            min_price=filter_data.min_price,
            max_price=filter_data.max_price,
            min_square=filter_data.min_square,
            rooms=filter_data.rooms,
            rental_type=RentalTypes.FULL_APARTMENT,
            gender=None,
            roommate_preference=None,
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/users/filters/room-sharing")
async def set_room_sharing_filter(filter_data: RoomSharingFilter):
    """Set filter for room sharing"""
    try:
        # Обновляем тип фильтра пользователя
        create_or_update_user(
            user_id=filter_data.user_id,
            filter_type=RentalTypes.ROOM_SHARING,
        )

        # Сохраняем фильтр
        save_user_filter(
            user_id=filter_data.user_id,
            city=filter_data.city,
            min_price=filter_data.min_price,
            max_price=filter_data.max_price,
            min_square=filter_data.min_square,
            rooms=filter_data.rooms,
            rental_type=RentalTypes.ROOM_SHARING,
            gender=filter_data.gender,
            roommate_preference=filter_data.roommate_preference,
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/users/{user_id}/filters")
async def delete_user_filter_endpoint(user_id: int):
    """Delete user filter"""
    try:
        # Убедимся, что пользователь существует
        if not is_user_active(user_id):
            raise HTTPException(status_code=404, detail="User not found or inactive")

        # Сбрасываем тип фильтра пользователя
        create_or_update_user(
            user_id=user_id,
            filter_type=None,
        )

        # Удаляем фильтр
        db_delete_user_filter(user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/filters/user/{user_id}")
async def get_filter_by_user_id(user_id: int):
    """Get filter for specific user"""
    try:
        if not is_user_active(user_id):
            raise HTTPException(status_code=404, detail="User not found or inactive")

        filter_data = get_user_filter(user_id)
        if not filter_data:
            return {}

        # Определяем тип фильтра и возвращаем соответствующую модель
        rental_type = filter_data.get("rental_type")

        if rental_type == RentalTypes.FULL_APARTMENT:
            return FullApartmentFilter(**filter_data)
        elif rental_type == RentalTypes.ROOM_SHARING:
            return RoomSharingFilter(**filter_data)
        else:
            return filter_data
    except Exception as e:
        logging.error(f"Error getting filter for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/apartments/{apartment_id}/photos")
def get_apartment_photos(apartment_id: int, max_photos: int = 3) -> List[Dict]:
    """
    Получает список фотографий для квартиры

    Args:
        apartment_id (int): ID квартиры
        max_photos (int): Максимальное количество фотографий

    Returns:
        List[Dict]: Список метаданных фотографий
    """
    session = SessionLocal()
    try:
        photos = (
            session.query(ApartmentPhoto)
            .filter(ApartmentPhoto.apartment_id == apartment_id)
            .order_by(ApartmentPhoto.order)
            .limit(max_photos)
            .all()
        )

        return [
            {
                "id": photo.id,
                "apartment_id": photo.apartment_id,
                "content_type": photo.content_type,
                "order": photo.order,
            }
            for photo in photos
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении фотографий: {str(e)}"
        )
    finally:
        session.close()


@app.get("/apartments/photos/{photo_id}")
def get_photo_data(photo_id: int):
    """
    Получает бинарные данные фотографии

    Args:
        photo_id (int): ID фотографии

    Returns:
        Response: Бинарные данные фотографии с соответствующим Content-Type
    """
    session = SessionLocal()
    try:
        photo = (
            session.query(ApartmentPhoto).filter(ApartmentPhoto.id == photo_id).first()
        )

        if not photo:
            raise HTTPException(status_code=404, detail="Фотография не найдена")

        return Response(content=photo.photo_data, media_type=photo.content_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении данных фотографии: {str(e)}"
        )
    finally:
        session.close()


@app.get("/telegram/apartments/{apartment_id}/photos")
def get_telegram_apartment_photos(apartment_id: int, max_photos: int = 3) -> List[Dict]:
    """
    Получает список фотографий для квартиры из Telegram

    Args:
        apartment_id (int): ID квартиры
        max_photos (int): Максимальное количество фотографий

    Returns:
        List[Dict]: Список метаданных фотографий
    """
    session = SessionLocal()
    try:
        photos = (
            session.query(TelegramApartmentPhoto)
            .filter(TelegramApartmentPhoto.apartment_id == apartment_id)
            .order_by(TelegramApartmentPhoto.created_at.desc())
            .limit(max_photos)
            .all()
        )

        return [
            {
                "id": str(photo.id),
                "apartment_id": photo.apartment_id,
                "created_at": photo.created_at.isoformat()
                if photo.created_at
                else None,
            }
            for photo in photos
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении фотографий: {str(e)}"
        )
    finally:
        session.close()


@app.get("/telegram/photos/{photo_id}")
def get_telegram_photo_data(photo_id: str):
    """
    Получает бинарные данные фотографии из Telegram

    Args:
        photo_id (str): ID фотографии (UUID)

    Returns:
        Response: Бинарные данные фотографии
    """
    session = SessionLocal()
    try:
        photo = (
            session.query(TelegramApartmentPhoto)
            .filter(TelegramApartmentPhoto.id == photo_id)
            .first()
        )

        if not photo:
            raise HTTPException(status_code=404, detail="Фотография не найдена")

        return Response(content=photo.photo_data, media_type="image/jpeg")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении данных фотографии: {str(e)}"
        )
    finally:
        session.close()

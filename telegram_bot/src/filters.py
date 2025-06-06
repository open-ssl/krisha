import logging
from typing import Dict, List, Optional


class UserFilters:
    """Class for storing user filters"""

    def __init__(self):
        """Initialize empty filters dictionary"""
        self.filters: Dict[int, dict] = {}

    def set_filter(
        self,
        user_id: int,
        city: Optional[str] = None,
        rooms: Optional[List[int]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_square: Optional[float] = None,
        rental_type: Optional[str] = None,
        gender: Optional[str] = None,
        roommate_preference: Optional[str] = None,
    ) -> None:
        """
        Set filter for user

        Args:
            user_id (int): User ID
            city (Optional[str], optional): City name. Defaults to None.
            rooms (Optional[List[int]], optional): List of room counts. Defaults to None.
            min_price (Optional[float], optional): Minimum price. Defaults to None.
            max_price (Optional[float], optional): Maximum price. Defaults to None.
            min_square (Optional[float], optional): Minimum square. Defaults to None.
            rental_type (Optional[str], optional): Rental type. Defaults to None.
            gender (Optional[str], optional): User gender. Defaults to None.
            roommate_preference (Optional[str], optional): Roommate preference. Defaults to None.
        """
        if all(
            param is None
            for param in [
                city,
                rooms,
                min_price,
                max_price,
                min_square,
                rental_type,
                gender,
                roommate_preference,
            ]
        ):
            if user_id in self.filters:
                del self.filters[user_id]
            return

        # Логируем значения для отладки
        logging.info(f"Setting filter for user {user_id}")
        logging.info(f"Gender: {gender}")
        logging.info(f"Roommate preference: {roommate_preference}")

        # Создаем или обновляем фильтр
        self.filters[user_id] = {
            "city": city,
            "rooms": rooms,
            "min_price": min_price,
            "max_price": max_price,
            "min_square": min_square,
            "rental_type": rental_type,
            "gender": gender,
            "roommate_preference": roommate_preference,
        }

        # Логируем сохраненный фильтр
        logging.info(f"Filter saved: {self.filters[user_id]}")

    def get_filter(self, user_id: int) -> Optional[dict]:
        """
        Get filter for user

        Args:
            user_id (int): User ID

        Returns:
            Optional[dict]: Filter data or None if not set
        """
        return self.filters.get(user_id)

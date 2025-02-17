from typing import Dict, Optional

class UserFilters:
    """Class for managing user filters"""
    
    def __init__(self):
        self.filters: Dict[int, Dict] = {}
        
    def set_filter(self, user_id: int, city: Optional[str] = None,
                  rooms: Optional[list] = None, min_price: Optional[float] = None,
                  max_price: Optional[float] = None) -> None:
        """
        Set filter for user
        
        Args:
            user_id (int): Telegram user ID
            city (str, optional): City filter
            rooms (list, optional): Room numbers
            min_price (float, optional): Minimum price
            max_price (float, optional): Maximum price
        """
        self.filters[user_id] = {
            "city": city,
            "rooms": rooms,
            "min_price": min_price,
            "max_price": max_price
        }
        
    def get_filter(self, user_id: int) -> Optional[Dict]:
        """
        Get user's filter
        
        Args:
            user_id (int): Telegram user ID
            
        Returns:
            Optional[Dict]: User's filter or None
        """
        return self.filters.get(user_id) 
import json
import redis
from typing import Dict, List
from database import is_user_active
import os
from dotenv import load_dotenv
import requests
import logging

load_dotenv()

class NotificationManager:
    """Manager for handling apartment notifications"""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is not set")
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        
    def get_user_seen_apartments(self, user_id: int) -> set:
        """Get set of apartments already seen by user"""
        return set(self.redis.smembers(f"user:{user_id}:seen_apartments"))
        
    def mark_apartments_as_seen(self, user_id: int, apartment_urls: List[str]) -> None:
        """Mark apartments as seen by user"""
        if apartment_urls:
            self.redis.sadd(f"user:{user_id}:seen_apartments", *apartment_urls)
            
    def notify_new_apartments(self, user_id: int, apartments: List[Dict]) -> None:
        """
        Notify about new apartments
        
        Args:
            user_id (int): Telegram user ID
            apartments (List[Dict]): List of new apartments
        """
        # Проверяем, активен ли пользователь перед отправкой уведомлений
        try:
            response = requests.get(f"{os.getenv('SCRAPER_SERVICE_URL')}/users/{user_id}/status")
            if not response.ok or not response.json().get('is_active', False):
                return
        except Exception as e:
            logging.error(f"Error checking user status: {e}")
            return
            
        seen_apartments = self.get_user_seen_apartments(user_id)
        new_apartments = [apt for apt in apartments if apt['url'] not in seen_apartments]
        
        if new_apartments:
            message = {
                'user_id': user_id,
                'apartments': new_apartments
            }
            self.redis.publish('new_apartments', json.dumps(message))
            self.mark_apartments_as_seen(user_id, [apt['url'] for apt in new_apartments]) 
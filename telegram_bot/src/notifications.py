import json
import asyncio
from typing import Optional
import aioredis
from message_manager import MessageManager
import os
from dotenv import load_dotenv

load_dotenv()

class NotificationHandler:
    """Handler for apartment notifications"""
    
    def __init__(self, message_manager: MessageManager, bot):
        """
        Initialize notification handler
        
        Args:
            message_manager (MessageManager): Message manager instance
            bot: Bot instance
        """
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is not set")
        self.redis_url = redis_url
        self.message_manager = message_manager
        self.bot = bot
        self.running = False
        
    async def start(self):
        """Start listening for notifications"""
        self.running = True
        self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe('new_apartments')
        
        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    await self.process_notification(data)
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe('new_apartments')
            await self.redis.close()
            
    async def process_notification(self, data: dict):
        """Process notification about new apartments"""
        user_id = data['user_id']
        apartments = data['apartments']
        
        if not apartments:
            return
            
        result_message = "🆕 Новые квартиры по вашим критериям:\n\n"
        for apt in apartments:
            location_parts = []
            if apt.get('district'):
                location_parts.append(f"р-н {apt['district']}")
            if apt.get('street'):
                location_parts.append(apt['street'])
            if apt.get('complex_name'):
                location_parts.append(f"(ЖК {apt['complex_name']})")
            
            location = ', '.join(filter(None, location_parts))
            
            result_message += (
                f"🏠 {apt['rooms']}-комн. {location}, "
                f"*{apt['price']} тг*\n"
                f"{apt['url']}\n\n"
            )
            
        await self.message_manager.send_message(
            self.bot,
            user_id,
            result_message,
            parse_mode="Markdown"
        ) 
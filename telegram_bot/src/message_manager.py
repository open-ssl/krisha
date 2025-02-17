import asyncio
from typing import Any, Optional
from aiogram import Bot, types
import time
from collections import deque
import requests
import logging
import os

class MessageManager:
    """Manager for handling message sending with rate limiting and priorities"""
    
    def __init__(self, messages_per_second: int = 3, admin_id: int = 465146483):
        """
        Initialize message manager
        
        Args:
            messages_per_second (int): Maximum messages per second
            admin_id (int): Telegram ID of admin user
        """
        self.messages_per_second = messages_per_second
        self.admin_id = admin_id
        self.regular_queue = deque()
        self.admin_queue = deque()
        self.last_send_time = time.time()
        self.messages_sent = 0
        self.lock = asyncio.Lock()
        self.processing = False
        
    async def send_message(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        reply_markup: Optional[types.ReplyKeyboardMarkup] = None,
        parse_mode: Optional[str] = None
    ) -> None:
        """
        Send message with rate limiting
        
        Args:
            bot (Bot): Telegram bot instance
            chat_id (int): Chat ID to send message to
            text (str): Message text
            reply_markup (Optional[types.ReplyKeyboardMarkup]): Optional keyboard markup
            parse_mode (Optional[str]): Message parse mode (e.g., "Markdown", "HTML")
        """
        message_data = {
            'chat_id': chat_id,
            'text': text,
            'reply_markup': reply_markup,
            'parse_mode': parse_mode
        }
        
        # Добавляем сообщение в соответствующую очередь
        if chat_id == self.admin_id:
            self.admin_queue.append(message_data)
        else:
            self.regular_queue.append(message_data)
            
        # Запускаем обработку очереди, если она еще не запущена
        if not self.processing:
            self.processing = True
            asyncio.create_task(self._process_queues(bot))
    
    async def _process_queues(self, bot: Bot) -> None:
        """Process message queues with rate limiting"""
        try:
            while self.admin_queue or self.regular_queue:
                async with self.lock:
                    current_time = time.time()
                    
                    # Сбрасываем счетчик каждую секунду
                    if current_time - self.last_send_time >= 1:
                        self.messages_sent = 0
                        self.last_send_time = current_time
                    
                    # Если достигнут лимит, ждем следующей секунды
                    if self.messages_sent >= self.messages_per_second:
                        await asyncio.sleep(1)
                        continue
                        
                    # Сначала обрабатываем сообщения для админа
                    if self.admin_queue:
                        message_data = self.admin_queue.popleft()
                        await self._send_message(bot, **message_data)
                        self.messages_sent += 1
                    # Затем обрабатываем обычные сообщения
                    elif self.regular_queue:
                        message_data = self.regular_queue.popleft()
                        await self._send_message(bot, **message_data)
                        self.messages_sent += 1
                
                # Небольшая пауза между отправками
                await asyncio.sleep(0.1)
        finally:
            self.processing = False
    
    async def _send_message(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        reply_markup: Optional[types.ReplyKeyboardMarkup] = None,
        parse_mode: Optional[str] = None
    ) -> None:
        """Actually send the message"""
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            if "Forbidden: bot was blocked by the user" in str(e):
                # Если пользователь заблокировал бота, обновляем его статус
                try:
                    response = requests.post(
                        f"{os.getenv('SCRAPER_SERVICE_URL')}/users",
                        json={
                            "user_id": chat_id,
                            "is_active": False
                        }
                    )
                    if not response.ok:
                        logging.error(f"Failed to update user block status: {response.status_code} - {response.text}")
                except Exception as update_error:
                    logging.error(f"Error updating user block status: {update_error}")
            logging.error(f"Error sending message: {e}") 
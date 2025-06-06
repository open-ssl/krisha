import logging
import asyncio
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from env import TELEGRAM_NOTIFICATION_BOT_TOKEN, TELEGRAM_ADMIN_ID

# Глобальные переменные
bot = None
dp = None
# Ссылка на брокер, которая будет установлена из main.py
broker = None
# Ссылка на pending_verification_requests, которая будет установлена из main.py
pending_verification_requests = None


def setup_broker_reference(broker_instance, pending_requests):
    """
    Устанавливает ссылку на брокер и словарь ожидающих запросов из main.py.
    
    Args:
        broker_instance: Экземпляр брокера RabbitMQ
        pending_requests: Словарь ожидающих запросов на верификацию
    """
    global broker, pending_verification_requests
    broker = broker_instance
    pending_verification_requests = pending_requests


def setup_bot():
    """
    Инициализация Telegram бота.
    """
    global bot, dp
    
    if bot is None:
        # Создаем экземпляр бота
        bot = Bot(token=TELEGRAM_NOTIFICATION_BOT_TOKEN)
        # Создаем диспетчер
        dp = Dispatcher()
        
        # Регистрируем обработчики
        register_handlers()
        
        logging.info("Telegram bot initialized successfully")


async def start_bot_polling():
    """
    Запуск бота в режиме polling.
    """
    global bot, dp
    
    if bot and dp:
        try:
            # Сначала удаляем webhook, чтобы избежать конфликта
            await bot.delete_webhook(drop_pending_updates=True)
            logging.info("Webhook deleted successfully")
            
            # Запускаем поллинг
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Error starting bot polling: {e}")


def register_handlers():
    """
    Регистрация обработчиков сообщений.
    """
    global dp
    
    if dp:
        # Обработчик команды /start
        @dp.message(Command("start"))
        async def cmd_start(message: Message):
            if str(message.from_user.id) == TELEGRAM_ADMIN_ID:
                await message.answer(
                    "Привет! Я бот для отправки уведомлений и обработки кодов подтверждения."
                )
        
        # Обработчик текстовых сообщений
        @dp.message()
        async def handle_message(message: Message):
            # Проверяем, является ли отправитель администратором
            if str(message.from_user.id) == TELEGRAM_ADMIN_ID:
                # Проверяем, может ли сообщение быть кодом подтверждения
                text = message.text.strip()
                if text.isdigit() or (len(text) <= 10 and not text.startswith("/")):
                    # Ищем ожидающий запрос на верификацию
                    for request_id, request_data in list(pending_verification_requests.items()):
                        if request_data.get("admin_id") == str(message.from_user.id) and request_data.get("status") == "pending":
                            # Отправляем код подтверждения в scraper_service
                            await send_verification_code(request_id, text)
                            
                            # Обновляем статус запроса
                            pending_verification_requests[request_id]["status"] = "completed"
                            
                            await message.answer(f"Код подтверждения {text} отправлен.")
                            return
                
                # Если сообщение не обработано как код подтверждения
                await message.answer("Получено сообщение. Если это код подтверждения, он будет отправлен автоматически.")


async def send_message_to_admin(admin_id: str, message: str) -> bool:
    """
    Отправка сообщения администратору.
    
    Args:
        admin_id (str): ID администратора
        message (str): Текст сообщения
        
    Returns:
        bool: True, если сообщение отправлено успешно, иначе False
    """
    global bot
    
    if bot:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode="Markdown")
            return True
        except Exception as e:
            logging.error(f"Error sending message to admin {admin_id}: {e}")
    
    return False


async def send_verification_code(request_id: str, verification_code: str) -> bool:
    """
    Отправка кода подтверждения в scraper_service.
    
    Args:
        request_id (str): ID запроса
        verification_code (str): Код подтверждения
        
    Returns:
        bool: True, если код отправлен успешно, иначе False
    """
    global broker
    
    if not broker:
        logging.error("Broker reference is not set")
        return False
    
    try:
        # Отправляем код подтверждения через брокер
        await broker.publish(
            {
                "request_id": request_id,
                "verification_code": verification_code
            },
            queue="verification_code_queue"
        )
        
        logging.info(f"Отправлен код подтверждения для запроса {request_id}: {verification_code}")
        return True
    except Exception as e:
        logging.error(f"Error sending verification code: {e}")
        return False 
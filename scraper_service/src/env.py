"""
Модуль для работы с переменными окружения.
Здесь происходит централизованная инициализация всех переменных окружения,
которые используются в проекте.
"""
import os
from typing import Optional

from dotenv import load_dotenv


# Загружаем переменные окружения из .env файла, если он существует
load_dotenv()

# Настройки подключения к БД
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
AUTHOR_URL: str = os.environ.get("AUTHOR_URL", "")
MAX_MESSAGE_LENGTH: int = int(os.environ.get("MAX_MESSAGE_LENGTH", "3500"))

# Настройки сервиса
SCRAPER_SERVICE_PORT: int = int(os.environ.get("SCRAPER_SERVICE_PORT", "8088"))
SCRAPER_SERVICE_URL: str = os.environ.get("SCRAPER_SERVICE_URL", "")

# Настройки для Redis
REDIS_URL: Optional[str] = os.environ.get("REDIS_URL", None)

# Настройки для Telegram
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "")
TELEGRAM_CLOUD_PASSWORD = os.getenv("TELEGRAM_CLOUD_PASSWORD", "")
TELEGRAM_NOTIFICATION_BOT_TOKEN = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")

# Идентификатор группы для парсинга
TELEGRAM_PARSE_GROUP1 = os.getenv("TELEGRAM_PARSE_GROUP1")
TELEGRAM_PARSE_GROUP_NAME1 = os.getenv("TELEGRAM_PARSE_GROUP_NAME1")

TELEGRAM_PARSE_GROUP2 = os.getenv("TELEGRAM_PARSE_GROUP2")
TELEGRAM_PARSE_GROUP_NAME2 = os.getenv("TELEGRAM_PARSE_GROUP_NAME2")

TELEGRAM_CHANNELS = [TELEGRAM_PARSE_GROUP1, TELEGRAM_PARSE_GROUP2]

MEDIA_FOLDER = os.getenv("MEDIA_FOLDER", "media/telegram_photos")

# API ключи для Together.ai
TOGETHER_API_KEYS = [
    os.getenv("TOGETHER_API_KEY1"),
    os.getenv("TOGETHER_API_KEY2"),
]

SKIPPED_PHOTO_INDEXES = [0, 2]

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

TELEGRAM_PARSE_GROUP_DICT = {
    TELEGRAM_PARSE_GROUP1: TELEGRAM_PARSE_GROUP_NAME1,
    TELEGRAM_PARSE_GROUP2: TELEGRAM_PARSE_GROUP_NAME2,
}

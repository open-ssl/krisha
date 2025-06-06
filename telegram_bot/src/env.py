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

# Основные настройки бота
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MAX_MESSAGE_LENGTH: int = int(os.environ.get("MAX_MESSAGE_LENGTH", "3500"))

# Настройки подключения к API
SCRAPER_SERVICE_URL: str = os.environ.get("SCRAPER_SERVICE_URL", "")

# Настройки для Redis
REDIS_HOST: str = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))

# Прочие настройки
AUTHOR_URL: Optional[str] = os.environ.get("AUTHOR_URL", None)

TELEGRAM_PARSE_GROUP1: Optional[int] = os.environ.get("TELEGRAM_PARSE_GROUP1", None)
TELEGRAM_PARSE_GROUP_NAME1: Optional[str] = os.environ.get(
    "TELEGRAM_PARSE_GROUP_NAME1", None
)

TELEGRAM_PARSE_GROUP2 = os.getenv("TELEGRAM_PARSE_GROUP2")
TELEGRAM_PARSE_GROUP_NAME2 = os.getenv("TELEGRAM_PARSE_GROUP_NAME2")


TELEGRAM_PARSE_GROUP_DICT = {
    TELEGRAM_PARSE_GROUP1: TELEGRAM_PARSE_GROUP_NAME1,
    TELEGRAM_PARSE_GROUP2: TELEGRAM_PARSE_GROUP_NAME2,
}

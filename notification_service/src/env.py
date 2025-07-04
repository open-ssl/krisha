import os

# Порт для FastAPI сервера
NOTIFICATION_SERVICE_PORT = int(os.getenv("NOTIFICATION_SERVICE_PORT", 8001))

# Настройки RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

# Настройки Telegram бота
TELEGRAM_NOTIFICATION_BOT_TOKEN = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Идентификатор группы для парсинга
TELEGRAM_PARSE_GROUP1 = os.getenv("TELEGRAM_PARSE_GROUP1")
TELEGRAM_PARSE_GROUP_NAME1 = os.getenv("TELEGRAM_PARSE_GROUP_NAME1")

TELEGRAM_PARSE_GROUP2 = os.getenv("TELEGRAM_PARSE_GROUP2")
TELEGRAM_PARSE_GROUP_NAME2 = os.getenv("TELEGRAM_PARSE_GROUP_NAME2")

TELEGRAM_PARSE_GROUP_DICT = {
    TELEGRAM_PARSE_GROUP1: TELEGRAM_PARSE_GROUP_NAME1,
    TELEGRAM_PARSE_GROUP2: TELEGRAM_PARSE_GROUP_NAME2
}


TOGETHER_API_KEY1 = os.getenv("TOGETHER_API_KEY1")
TOGETHER_API_KEY2 = os.getenv("TOGETHER_API_KEY2")
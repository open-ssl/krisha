# Notification Service

Сервис для отправки уведомлений через Telegram и обработки кодов подтверждения.

## Описание

Notification Service - это микросервис, который обрабатывает запросы на получение кодов подтверждения от Scraper Service и взаимодействует с пользователем через Telegram бота. Когда Scraper Service нуждается в коде подтверждения для авторизации в Telegram, он отправляет запрос в Notification Service через Kafka. Notification Service отправляет сообщение администратору через Telegram бота и ожидает ответа. Когда администратор отвечает с кодом подтверждения, Notification Service отправляет этот код обратно в Scraper Service через Kafka.

## Технологии

- Python 3.11
- FastAPI
- Aiogram 3.0
- FastStream (для работы с Kafka)
- Poetry (для управления зависимостями)
- Docker

## Установка и запуск

### Локальная разработка

1. Установите Poetry:
   ```bash
   pip install poetry
   ```

2. Установите зависимости:
   ```bash
   poetry install
   ```

3. Запустите сервис:
   ```bash
   poetry run python src/main.py
   ```

### Запуск с Docker

```bash
docker-compose up notification_service
```

## Переменные окружения

- `NOTIFICATION_SERVICE_PORT` - порт для FastAPI сервера (по умолчанию 8001)
- `KAFKA_BOOTSTRAP_SERVERS` - адрес серверов Kafka (по умолчанию "kafka:9092")
- `TELEGRAM_NOTIFICATION_BOT_TOKEN` - токен Telegram бота
- `TELEGRAM_ADMIN_ID` - ID администратора в Telegram 
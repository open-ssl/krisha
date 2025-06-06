import asyncio
import logging
import threading
import uuid
from typing import Optional

from faststream.rabbit import RabbitBroker

from src.env import RABBITMQ_URL, TELEGRAM_ADMIN_ID


# Глобальные переменные
broker = None
verification_codes = {}
verification_code_lock = threading.Lock()
# Добавляем глобальную переменную для хранения цикла событий
event_loop = None
# Добавляем глобальную переменную для отслеживания активного запроса на подтверждение
active_verification_request = None
# Добавляем блокировку для доступа к active_verification_request
active_request_lock = threading.Lock()


async def initialize_broker():
    """
    Инициализация брокера RabbitMQ.

    Returns:
        RabbitBroker: Инициализированный брокер
    """
    global broker, event_loop

    # Сохраняем текущий цикл событий
    event_loop = asyncio.get_running_loop()

    if broker is None:
        try:
            # Создаем брокер
            broker = RabbitBroker(RABBITMQ_URL)

            # Запускаем брокер
            await broker.start()

            # Регистрируем обработчик для получения кодов подтверждения
            @broker.subscriber("verification_code_queue")
            async def handle_verification_code(code_data: dict):
                request_id = code_data.get("request_id")
                verification_code = code_data.get("verification_code")

                if not request_id or not verification_code:
                    logging.error(
                        f"Получен некорректный ответ с кодом верификации: {code_data}"
                    )
                    return

                # Сохраняем код подтверждения
                with verification_code_lock:
                    verification_codes[request_id] = verification_code

                # Очищаем активный запрос, если это он
                with active_request_lock:
                    global active_verification_request
                    if active_verification_request == request_id:
                        active_verification_request = None

                logging.info(
                    f"Получен код подтверждения для запроса {request_id}: {verification_code}"
                )

            logging.info("RabbitMQ broker initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize RabbitMQ broker: {e}")

    return broker


async def request_verification_code(message: str) -> Optional[str]:
    """
    Запрос кода подтверждения у пользователя через notification_service.

    Args:
        message (str): Сообщение для пользователя

    Returns:
        Optional[str]: Код подтверждения или None, если не удалось получить код
    """
    global broker, event_loop, active_verification_request

    # Проверяем, есть ли уже активный запрос на подтверждение
    with active_request_lock:
        if active_verification_request is not None:
            # Если есть активный запрос, ждем его завершения
            request_id = active_verification_request
            logging.info(
                f"Уже есть активный запрос на подтверждение с ID {request_id}, ожидаем его завершения"
            )
        else:
            # Если нет активного запроса, создаем новый
            request_id = str(uuid.uuid4())
            active_verification_request = request_id

            # Инициализируем брокер, если он еще не инициализирован
            if broker is None:
                await initialize_broker()

            if broker is None:
                logging.error("Failed to initialize RabbitMQ broker")
                with active_request_lock:
                    active_verification_request = None
                return None

            # Отправляем запрос на верификацию
            try:
                # Убедимся, что мы используем правильный цикл событий
                if event_loop and event_loop != asyncio.get_running_loop():
                    logging.warning(
                        "Detected different event loop, using the original one for publishing"
                    )
                    future = asyncio.run_coroutine_threadsafe(
                        broker.publish(
                            {
                                "request_id": request_id,
                                "message": message,
                                "admin_id": TELEGRAM_ADMIN_ID,
                            },
                            queue="verification_request_queue",
                        ),
                        event_loop,
                    )
                    # Ждем завершения публикации
                    future.result()
                else:
                    # Используем текущий цикл событий
                    await broker.publish(
                        {
                            "request_id": request_id,
                            "message": message,
                            "admin_id": TELEGRAM_ADMIN_ID,
                        },
                        queue="verification_request_queue",
                    )

                logging.info(f"Отправлен запрос на верификацию с ID {request_id}")
            except Exception as e:
                logging.error(f"Error publishing verification request: {e}")
                with active_request_lock:
                    active_verification_request = None
                return None

    # Ожидаем получения кода подтверждения
    for _ in range(30):
        with verification_code_lock:
            if request_id in verification_codes:
                code = verification_codes.pop(request_id)
                # Очищаем активный запрос, если это он
                with active_request_lock:
                    if active_verification_request == request_id:
                        active_verification_request = None
                return code
        await asyncio.sleep(10)

    # Если время ожидания истекло, очищаем активный запрос
    with active_request_lock:
        if active_verification_request == request_id:
            active_verification_request = None

    logging.error(f"Таймаут ожидания кода подтверждения для запроса {request_id}")
    return None


async def close_broker():
    """
    Закрытие брокера RabbitMQ.
    """
    global broker

    if broker:
        await broker.close()
        logging.info("RabbitMQ broker closed")

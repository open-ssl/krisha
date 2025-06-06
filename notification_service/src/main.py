import logging
import asyncio
from dotenv import load_dotenv

from fastapi import FastAPI
from faststream.rabbit import RabbitBroker
import uvicorn

from env import NOTIFICATION_SERVICE_PORT, RABBITMQ_URL, TELEGRAM_PARSE_GROUP_DICT

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Создаем FastAPI приложение
app = FastAPI(title="Notification Service")


# Создаем брокер RabbitMQ
broker = RabbitBroker(RABBITMQ_URL)

# Глобальная переменная для хранения ожидающих кодов подтверждения
pending_verification_requests = {}

# Импортируем и устанавливаем ссылку на брокер в bot.py
from bot import setup_broker_reference
setup_broker_reference(broker, pending_verification_requests)


@broker.subscriber("verification_request_queue")
async def handle_verification_request(request_data: dict):
    """
    Обработчик запросов на получение кода подтверждения от scraper_service.
    
    Args:
        request_data (dict): Данные запроса, содержащие request_id и сообщение для пользователя
    """
    request_id = request_data.get("request_id")
    message = request_data.get("message", "Требуется код подтверждения для Telegram. Пожалуйста, отправьте код.")
    admin_id = request_data.get("admin_id")
    
    if not request_id or not admin_id:
        logging.error(f"Получен некорректный запрос на верификацию: {request_data}")
        return
    
    # Сохраняем запрос в ожидающие
    pending_verification_requests[request_id] = {
        "admin_id": admin_id,
        "status": "pending"
    }
    
    # Импортируем здесь, чтобы избежать циклического импорта
    from bot import send_message_to_admin
    await send_message_to_admin(admin_id, message)
    
    logging.info(f"Отправлен запрос на верификацию с ID {request_id} администратору {admin_id}")


@broker.subscriber("send_channel_post")
async def handle_channel_post(request_data: dict):
    """
    Обработчик запросов на отправку сообщений в канал.

    Args:
        request_data (dict): Данные запроса, содержащие request_id и сообщение для пользователя
    """
    # # Импортируем здесь, чтобы избежать циклического импорта
    from bot import send_message_to_admin

    community_id = request_data["community_id"]
    apartments = request_data["apartments"]
    apartment_type = request_data["apartment_type"]

    apartments_amount = len(apartments)
    if apartments_amount > 2:
        # показываем только 2 последних объявления если их много
        apartments = apartments[:2]
        apartments_amount = apartments_amount - 2

    if apartment_type == "full_apartment":
        city_name = ""
        first_apt = apartments[0]
        if first_apt.get("city"):
            # Используем название города с большой буквы
            city_name = first_apt["city"].capitalize()

        result_message = "Появились новые предложения!\n\n🆕 Жильё целиком\n"
        if city_name:
            result_message += f"🏙️ Город: #{city_name}\n"

        if first_apt.get("price"):
            price1 = first_apt.get("price")
            price = int(price1)
            if len(apartments) == 2:
                second_apt = apartments[1]
                price = min([int(second_apt.get("price")), price])

            result_message += f"💰 Цена: #от{int(price)}\n"

        result_message += "\n"

        for apt in apartments:
            location = ""
            if apt.get("street"):
                location = apt["street"]

            result_message += f"🏠 {apt['rooms']}-комн., {apt['square']} м²\n"
            if location:
                result_message += f"📍 {location}\n"

            result_message += (
                f"💰 *{int(apt['price'])} тг*\n"
                f"[Ссылка на объявление]({apt['url']})\n\n"
            )

    else:
        result_message = "Появились новые предложения!\n\n🏢 Подселение\n"

        city_name = ""
        first_apt = apartments[0]
        if first_apt.get("city"):
            # Используем название города с большой буквы
            city_name = first_apt["city"].capitalize()

        if city_name:
            result_message += f"🏙️ Город: #{city_name}\n"

        if first_apt.get("price"):
            price1 = first_apt.get("price")
            price = int(price1)
            if len(apartments) == 2:
                second_apt = apartments[1]
                price = min([int(second_apt.get("price")), price])

            result_message += f"💰 Цена: #от{int(price)}\n"

        if first_apt.get("preferred_gender"):
            gender_text = {
                "boy": "Мужской",
                "girl": "Женский",
                "both": "Любой",
                "no": "Не указано",
            }.get(first_apt.get("preferred_gender"), "Не указано")
            result_message += f"👤 Предпочтительный пол: {gender_text}\n"

        result_message += "\n"

        for apt in apartments:
            price = (
                f"{apt.get('price')} тенге/месяц"
                if apt.get("price")
                else "Не указана"
            )

            result_message += (
                f"💰 *Цена:* {price}\n"
                f"📍 *Местоположение:* {apt.get('location', 'Не указано')}\n"
            )
            if apt.get("preferred_gender"):
                gender_text = {
                    "boy": "Мужской",
                    "girl": "Женский",
                    "both": "Любой",
                    "no": "Не указано",
                }.get(apt.get("preferred_gender"), "Не указано")
                result_message += f"👤 *Предпочтительный пол:* {gender_text}\n"

            if apt.get("contact"):
                result_message += f"📞 *Контакт:* {apt.get('contact')}\n"

            if apt.get("text"):
                # Ограничиваем длину текста
                text = apt.get("text")
                if len(text) > 200:  # Уменьшаем лимит для группировки
                    text = text[:197] + "..."
                result_message += f"\n*Описание:*\n{text}\n"

            if apt.get("channel") and apt.get("message_id"):
                channel = apt.get("channel")
                message_id = apt.get("message_id")

                channel_name = TELEGRAM_PARSE_GROUP_DICT.get(channel)
                if channel_name:
                    result_message += f"\n[Оригинальное объявление](https://t.me/{channel_name}/{message_id})\n\n"
            else:
                result_message += "\n\n"

    if apartments_amount > 1:
        result_message += f"По фильтру дополнительно найдено *{apartments_amount}* вариантов\n\n"

    result_message += f"Для поиска квартир в другом городе или с другим фильтром:"
    result_message += f"\n🚀🚀🚀[Запустить бесплатного бота для поиска квартир](https://t.me/rent_service_kz_bot)"

    await send_message_to_admin(community_id, result_message)
    await asyncio.sleep(1)

    logging.info(f"Отправлено сообщение в канал")


@app.on_event("startup")
async def startup_event():
    """
    Выполняется при запуске приложения.
    """
    # Импортируем здесь, чтобы избежать циклического импорта
    from bot import setup_bot, start_bot_polling
    
    # Инициализируем бота
    setup_bot()
    
    # Запускаем брокер
    await broker.start()
    
    # Запускаем бота в режиме polling в отдельном потоке
    asyncio.create_task(start_bot_polling())
    
    logging.info("Notification service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Выполняется при остановке приложения.
    """
    # Останавливаем брокер
    await broker.close()
    
    logging.info("Notification service stopped")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=NOTIFICATION_SERVICE_PORT)

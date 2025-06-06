import asyncio
import json
import logging
from typing import Optional

from aiogram.enums.parse_mode import ParseMode
from redis.asyncio import Redis

from env import MAX_MESSAGE_LENGTH, REDIS_HOST, REDIS_PORT, TELEGRAM_PARSE_GROUP_DICT
from message_manager import MessageManager
from src.utils.rental_types import RentalTypes
from utils.photo_manager import PhotoManager


class NotificationHandler:
    """Handler for apartment notifications"""

    def __init__(self, message_manager: MessageManager, bot):
        """
        Initialize notification handler

        Args:
            message_manager (MessageManager): Message manager instance
            bot: Bot instance
        """
        self.redis_host = REDIS_HOST
        self.redis_port = REDIS_PORT
        self.redis: Optional[Redis] = None
        self.message_manager = message_manager
        self.bot = bot
        self.running = False
        self.photo_manager = PhotoManager()
        self.scraper_service_url = "http://localhost:8000"  # Assuming a default URL

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = Redis(
                host=self.redis_host, port=self.redis_port, decode_responses=True
            )
            await self.redis.ping()
            logging.info("Successfully connected to Redis")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()

    async def start(self):
        """Start listening for notifications"""
        self.running = True
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("new_apartments")

        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    await self.process_notification(data)
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe("new_apartments")
            await self.disconnect()

    async def process_notification(self, data: dict):
        """
        Process notification about new apartments

        Args:
            data (dict): Notification data containing user_id, apartments and apartment_type
        """
        notification_type = data["type"]

        apartments = data["apartments"]
        apartment_type = data.get("apartment_type")

        if not apartments:
            return

        if notification_type == "user":
            user_id = data["user_id"]
            # Обрабатываем разные типы квартир
            if apartment_type == RentalTypes.ROOM_SHARING:
                # Логика для подселения
                await self._process_room_sharing_notification(user_id, apartments)
            elif apartment_type == RentalTypes.FULL_APARTMENT:
                # Логика для полной аренды квартиры
                await self._process_full_apartment_notification(user_id, apartments)

    async def _process_full_apartment_notification(self, user_id, apartments):
        """
        Обрабатывает уведомления о полной аренде квартиры

        Args:
            user_id (int): ID пользователя
            apartments (list): Список квартир для полной аренды
        """
        # Если только одна квартира, отправляем с фотографиями
        if len(apartments) == 1:
            apartment = apartments[0]

            # Формируем сообщение для одной квартиры
            result_message = "🆕 Новая квартира по вашим критериям:\n\n"

            if apartment.get("city"):
                city_name = apartment["city"].capitalize()
                result_message = (
                    f"🆕 Новая квартира по вашим критериям в городе **{city_name}**:\n\n"
                )

            location = ""
            if apartment.get("street"):
                location = apartment["street"]

            result_message += (
                f"🏠 {apartment['rooms']}-комн., {apartment['square']} м²\n"
            )
            if location:
                result_message += f"📍 {location}\n"

            result_message += (
                f"💰 *{int(apartment['price'])} тг*\n"
                f"[Ссылка на объявление]({apartment['url']})\n\n"
            )

            # Получаем фотографии для квартиры
            photos = None
            if apartment.get("id"):
                photos = self.photo_manager.get_apartment_photos(apartment["id"])
                logging.info(
                    f"Found {len(photos)} photos for apartment {apartment['id']}"
                )

            # Отправляем сообщение с фотографиями
            await self.message_manager.send_message(
                self.bot,
                user_id,
                result_message,
                parse_mode=ParseMode.MARKDOWN,
                photos=photos,
            )

            return

        # Для нескольких квартир отправляем без фотографий
        # Разбиваем квартиры на группы по 10 штук
        chunk_size = 10
        apartment_chunks = [
            apartments[index : index + chunk_size]
            for index in range(0, len(apartments), chunk_size)
        ]

        for chunk in apartment_chunks:
            # Проверяем, указан ли город у первой квартиры
            result_message = "🆕 Новые квартиры по вашим критериям:\n\n"
            first_apt = chunk[0]
            if first_apt.get("city"):
                # Используем название города с большой буквы
                city_name = first_apt["city"].capitalize()
                result_message = (
                    f"🆕 Новые квартиры по вашим критериям в городе **{city_name}**:\n\n"
                )

            for apt in chunk:
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

            await self.message_manager.send_message(
                self.bot, user_id, result_message, parse_mode=ParseMode.MARKDOWN
            )

            # Небольшая пауза между сообщениями
            await asyncio.sleep(1)

    async def _process_room_sharing_notification(self, user_id, apartments):
        """
        Обрабатывает уведомления о подселении

        Args:
            user_id (int): ID пользователя
            apartments (list): Список квартир для подселения
        """
        # Если только одна квартира, отправляем с фотографиями
        if len(apartments) == 1:
            apartment = apartments[0]

            # Формируем текст сообщения
            message_text = "🆕 Новое объявление о подселении по вашим критериям:\n\n"
            message_text += self._format_room_sharing_text(apartment)

            # Получаем фотографии для квартиры
            photos = None
            if apartment.get("id"):
                photos = self.photo_manager.get_telegram_apartment_photos(
                    apartment["id"]
                )
                logging.info(
                    f"Found {len(photos)} photos for telegram apartment {apartment['id']}"
                )

            # Отправляем сообщение с фотографиями
            await self.message_manager.send_message(
                self.bot,
                user_id,
                message_text,
                parse_mode=ParseMode.MARKDOWN,
                photos=photos,
            )

            return

        # Разбиваем квартиры на группы, учитывая длину сообщения
        current_message = (
            "🆕 Найдены новые объявления о подселении по вашим критериям:\n\n"
        )
        current_apartments = []

        for apartment in apartments:
            # Форматируем текст для текущего объявления
            apartment_text = self._format_room_sharing_text(apartment)

            # Проверяем, поместится ли объявление в текущее сообщение
            if len(current_message) + len(apartment_text) <= MAX_MESSAGE_LENGTH:
                current_message += apartment_text
                current_apartments.append(apartment)
            else:
                # Если не поместится, отправляем текущее сообщение и начинаем новое
                await self.message_manager.send_message(
                    self.bot, user_id, current_message, parse_mode=ParseMode.MARKDOWN
                )

                # Небольшая пауза между сообщениями
                await asyncio.sleep(1)

                # Начинаем новое сообщение
                current_message = "🆕 Новые объявления о подселении (продолжение):\n\n"
                current_message += apartment_text
                current_apartments = [apartment]

        # Отправляем последнее сообщение, если оно не пустое
        if (
            current_message != "🆕 Новые объявления о подселении:\n\n"
            and current_message != "🆕 Новые объявления о подселении (продолжение):\n\n"
        ):
            await self.message_manager.send_message(
                self.bot, user_id, current_message, parse_mode=ParseMode.MARKDOWN
            )

    def _format_room_sharing_text(self, apartment):
        """
        Форматирует текст объявления о подселении

        Args:
            apartment (dict): Данные объявления

        Returns:
            str: Отформатированный текст
        """
        price = (
            f"{apartment.get('price')} тенге/месяц"
            if apartment.get("price")
            else "Не указана"
        )

        message_text = (
            f"🏢 *Подселение*\n"
            f"💰 *Цена:* {price}\n"
            f"📍 *Местоположение:* {apartment.get('location', 'Не указано')}\n"
        )

        if apartment.get("preferred_gender"):
            gender_text = {
                "boy": "Мужской",
                "girl": "Женский",
                "both": "Любой",
                "no": "Не указано",
            }.get(apartment.get("preferred_gender"), "Не указано")
            message_text += f"👤 *Предпочтительный пол:* {gender_text}\n"

        if apartment.get("contact"):
            message_text += f"📞 *Контакт:* {apartment.get('contact')}\n"

        # Добавляем текст объявления, если он есть
        if apartment.get("text"):
            # Ограничиваем длину текста
            text = apartment.get("text")
            if len(text) > 200:  # Уменьшаем лимит для группировки
                text = text[:197] + "..."
            message_text += f"\n*Описание:*\n{text}\n"

        # Добавляем ссылку на оригинальное сообщение в Telegram
        if apartment.get("channel") and apartment.get("message_id"):
            channel = apartment.get("channel")
            message_id = apartment.get("message_id")

            channel_name = TELEGRAM_PARSE_GROUP_DICT.get(channel)
            if channel_name:
                message_text += f"\n[Оригинальное объявление](https://t.me/{channel_name}/{message_id})\n\n"
        else:
            message_text += "\n\n"

        return message_text

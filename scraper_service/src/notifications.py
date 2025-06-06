import asyncio
import json
import logging
from typing import Dict, List

import redis
import requests
from dotenv import load_dotenv

from database import (
    mark_community_full_apartments_as_seen_bulk,
    mark_community_telegram_apartments_as_seen_bulk,
    mark_full_apartments_as_seen_bulk,
    mark_telegram_apartments_as_seen_bulk,
)
from env import REDIS_URL, SCRAPER_SERVICE_URL
from src.utils.rental_types import RentalTypes


load_dotenv()


class NotificationManager:
    """Manager for handling apartment notifications"""

    def __init__(self):
        if not REDIS_URL:
            raise ValueError("REDIS_URL environment variable is not set")
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def get_user_seen_full_apartments(self, user_id: int) -> set:
        """Get set of full apartments already seen by user"""
        return set(self.redis.smembers(f"user:{user_id}:seen_full_apartments"))

    def get_user_seen_sharing_apartments(self, user_id: int) -> set:
        """Get set of sharing apartments already seen by user"""
        return set(self.redis.smembers(f"user:{user_id}:seen_sharing_apartments"))

    def get_community_seen_full_apartments(self, community_id: int) -> set:
        """Get set of full apartments already seen by community"""
        return set(
            self.redis.smembers(f"community:{community_id}:seen_full_apartments")
        )

    def get_community_seen_sharing_apartments(self, community_id: int) -> set:
        """Get set of sharing apartments already seen by community"""
        return set(
            self.redis.smembers(f"community:{community_id}:seen_sharing_apartments")
        )

    def mark_full_apartments_as_seen(
        self, user_id: int, apartment_urls: List[str]
    ) -> None:
        """Mark full apartments as seen by user"""
        if apartment_urls:
            self.redis.sadd(f"user:{user_id}:seen_full_apartments", *apartment_urls)

    def mark_sharing_apartments_as_seen(
        self, user_id: int, apartment_ids: List[str]
    ) -> None:
        """Mark sharing apartments as seen by user"""
        if apartment_ids:
            self.redis.sadd(f"user:{user_id}:seen_sharing_apartments", *apartment_ids)

    def mark_community_full_apartments_as_seen(
        self, community_id: int, apartment_urls: List[str]
    ) -> None:
        """Mark full apartments as seen by community"""
        if apartment_urls:
            self.redis.sadd(
                f"community:{community_id}:seen_full_apartments", *apartment_urls
            )

    def mark_community_sharing_apartments_as_seen(
        self, community_id: int, apartment_ids: List[str]
    ) -> None:
        """Mark sharing apartments as seen by community"""
        if apartment_ids:
            self.redis.sadd(
                f"community:{community_id}:seen_sharing_apartments", *apartment_ids
            )

    def notify_user_new_apartments(
        self, user_id: int, apartments: List[Dict], apartment_type: str
    ) -> None:
        """
        Notify about new apartments and mark them as seen

        Args:
            user_id (int): Telegram user ID
            apartments (List[Dict]): List of new apartments
            apartment_type (str): Type of apartment
        """
        # Проверяем, активен ли пользователь перед отправкой уведомлений
        try:
            response = requests.get(f"{SCRAPER_SERVICE_URL}/users/{user_id}/status")
            if not response.ok or not response.json().get("is_active", False):
                return
        except Exception as e:
            logging.error(f"Error checking user status: {e}")
            return

        if apartment_type == RentalTypes.FULL_APARTMENT:
            full_seen_apartments = self.get_user_seen_full_apartments(user_id)
            full_new_apartments = [
                apt for apt in apartments if apt["url"] not in full_seen_apartments
            ]

            if full_new_apartments:
                # Убеждаемся, что в каждой квартире включена информация о городе
                for apt in full_new_apartments:
                    if "city" not in apt and apt.get("city") is None:
                        logging.warning(
                            f"Apartment without city information: {apt['url']}"
                        )

                message = {
                    "type": "user",
                    "user_id": user_id,
                    "apartments": full_new_apartments,
                    "apartment_type": apartment_type,
                }
                self.redis.publish("new_apartments", json.dumps(message))

                # Отмечаем квартиры как просмотренные в Redis
                self.mark_full_apartments_as_seen(
                    user_id, [apt["url"] for apt in full_new_apartments]
                )

                # Собираем ID всех квартир, которые нужно отметить как просмотренные
            apartment_ids = []
            for apt in full_new_apartments:
                if "id" in apt:
                    apartment_ids.append(apt["id"])
                else:
                    logging.warning(
                        f"Apartment without ID cannot be marked as seen in DB: {apt['url']}"
                    )

                # Отмечаем квартиры как просмотренные в базе данных PostgreSQL одним запросом
            if apartment_ids:
                try:
                    mark_full_apartments_as_seen_bulk(
                        user_id=user_id,
                        apartment_ids=apartment_ids,
                        apartment_type=apartment_type,
                    )
                except Exception as e:
                    logging.error(f"Failed to mark apartments as seen in DB: {e}")
        elif apartment_type == RentalTypes.ROOM_SHARING:
            sharing_seen_apartments = self.get_user_seen_sharing_apartments(user_id)
            sharing_new_apartments = [
                apt for apt in apartments if apt["id"] not in sharing_seen_apartments
            ]

            if sharing_new_apartments:
                # Убеждаемся, что в каждой квартире включена информация о городе
                for apt in sharing_new_apartments:
                    if "city" not in apt and apt.get("city") is None:
                        logging.warning(
                            f"Apartment without city information: {apt['id']}"
                        )

                message = {
                    "type": "user",
                    "user_id": user_id,
                    "apartments": sharing_new_apartments,
                    "apartment_type": apartment_type,
                }
                self.redis.publish("new_apartments", json.dumps(message))

                # Отмечаем квартиры как просмотренные в Redis
                self.mark_sharing_apartments_as_seen(
                    user_id, [apt["id"] for apt in sharing_new_apartments]
                )

            apartment_ids = []
            for apt in sharing_new_apartments:
                if "id" in apt:
                    apartment_ids.append(apt["id"])
                else:
                    logging.warning(
                        f"Apartment without ID cannot be marked as seen in DB: {apt['id']}"
                    )

            if apartment_ids:
                try:
                    # apartment_type = RentalTypes.ROOM_SHARING
                    mark_telegram_apartments_as_seen_bulk(
                        user_id=user_id,
                        apartment_ids=apartment_ids,
                    )
                except Exception as e:
                    logging.error(f"Failed to mark apartments as seen in DB: {e}")

    def notify_community_new_apartments(
        self, broker, community_id: int, apartments: List[Dict], apartment_type: str
    ) -> None:
        """
        Notify about new apartments and mark them as seen

        Args:
            community_id (int): Telegram community ID
            apartments (List[Dict]): List of new apartments
            apartment_type (str): Type of apartment
        """
        if apartment_type == RentalTypes.FULL_APARTMENT:
            full_seen_apartments = self.get_community_seen_full_apartments(community_id)
            full_new_apartments = [
                apt for apt in apartments if apt["url"] not in full_seen_apartments
            ]

            if full_new_apartments:
                for apt in full_new_apartments:
                    if "city" not in apt and apt.get("city") is None:
                        logging.warning(
                            f"Apartment without city information: {apt['url']}"
                        )

                message = {
                    "type": "community",
                    "community_id": community_id,
                    "apartments": full_new_apartments,
                    "apartment_type": apartment_type,
                }

                try:
                    event_loop = asyncio.get_running_loop()
                except Exception:
                    event_loop = None

                try:
                    if event_loop and event_loop != asyncio.get_running_loop():
                        future = asyncio.run_coroutine_threadsafe(
                            broker.publish(
                                message,
                                queue="send_channel_post",
                            ),
                            event_loop,
                        )
                        future.result()
                    else:
                        asyncio.run(
                            broker.publish(
                                message,
                                queue="send_channel_post",
                            ),
                        )
                except Exception as e:
                    logging.error(e)

                # Отмечаем квартиры как просмотренные в Redis
                self.mark_community_full_apartments_as_seen(
                    community_id, [apt["url"] for apt in full_new_apartments]
                )

                # Собираем ID всех квартир, которые нужно отметить как просмотренные
            apartment_ids = []
            for apt in full_new_apartments:
                if "id" in apt:
                    apartment_ids.append(apt["id"])
                else:
                    logging.warning(
                        f"Apartment without ID cannot be marked as seen in DB: {apt['url']}"
                    )

                # Отмечаем квартиры как просмотренные в базе данных PostgreSQL одним запросом
            if apartment_ids:
                try:
                    mark_community_full_apartments_as_seen_bulk(
                        community_id=community_id,
                        apartment_ids=apartment_ids,
                        apartment_type=apartment_type,
                    )
                except Exception as e:
                    logging.error(f"Failed to mark apartments as seen in DB: {e}")
        elif apartment_type == RentalTypes.ROOM_SHARING:
            sharing_seen_apartments = self.get_community_seen_sharing_apartments(
                community_id=community_id
            )
            sharing_new_apartments = [
                apt for apt in apartments if apt["id"] not in sharing_seen_apartments
            ]

            if sharing_new_apartments:
                # Убеждаемся, что в каждой квартире включена информация о городе
                for apt in sharing_new_apartments:
                    if "city" not in apt and apt.get("city") is None:
                        logging.warning(
                            f"Apartment without city information: {apt['id']}"
                        )

                message = {
                    "type": "community",
                    "community_id": community_id,
                    "apartments": sharing_new_apartments,
                    "apartment_type": apartment_type,
                }

                try:
                    event_loop = asyncio.get_running_loop()
                except Exception:
                    event_loop = None

                try:
                    if event_loop and event_loop != asyncio.get_running_loop():
                        future = asyncio.run_coroutine_threadsafe(
                            broker.publish(
                                broker.publish(
                                    message,
                                    queue="send_channel_post",
                                )
                            ),
                            event_loop,
                        )
                        future.result()
                    else:
                        asyncio.run(
                            broker.publish(
                                message,
                                queue="send_channel_post",
                            ),
                        )
                except Exception as e:
                    logging.error(e)

                # Отмечаем квартиры как просмотренные в Redis
                self.mark_community_sharing_apartments_as_seen(
                    community_id, [apt["id"] for apt in sharing_new_apartments]
                )

            apartment_ids = []
            for apt in sharing_new_apartments:
                if "id" in apt:
                    apartment_ids.append(apt["id"])
                else:
                    logging.warning(
                        f"Apartment without ID cannot be marked as seen in DB: {apt['id']}"
                    )

            if apartment_ids:
                try:
                    # apartment_type = RentalTypes.ROOM_SHARING
                    mark_community_telegram_apartments_as_seen_bulk(
                        community_id=community_id,
                        apartment_ids=apartment_ids,
                    )
                except Exception as e:
                    logging.error(f"Failed to mark apartments as seen in DB: {e}")

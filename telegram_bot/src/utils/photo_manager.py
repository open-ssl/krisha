import logging
import os
import tempfile
from typing import List

import requests

from src.env import SCRAPER_SERVICE_URL


class PhotoManager:
    """Менеджер для работы с фотографиями квартир"""

    def __init__(self):
        """
        Инициализация менеджера фотографий
        """
        pass

    def get_apartment_photos(self, apartment_id: int, max_photos: int = 3) -> List[str]:
        """
        Получает фотографии квартиры из API скрапера

        Args:
            apartment_id (int): ID квартиры
            max_photos (int): Максимальное количество фотографий для возврата

        Returns:
            List[str]: Список путей к временным файлам с фотографиями
        """
        try:
            # Запрашиваем фотографии через API
            response = requests.get(
                f"{SCRAPER_SERVICE_URL}/apartments/{apartment_id}/photos",
                params={"max_photos": max_photos},
            )

            if not response.ok:
                logging.error(
                    f"Не удалось получить фотографии для квартиры {apartment_id}. Код статуса: {response.status_code}"
                )
                return []

            photos_data = response.json()
            temp_files = []

            # Создаем временные файлы для каждой фотографии
            for i, photo in enumerate(photos_data):
                try:
                    # Получаем бинарные данные фотографии
                    photo_response = requests.get(
                        f"{SCRAPER_SERVICE_URL}/apartments/photos/{photo['id']}"
                    )

                    if not photo_response.ok:
                        continue

                    # Определяем расширение файла
                    content_type = photo_response.headers.get(
                        "Content-Type", "image/jpeg"
                    )
                    ext = ".jpg"
                    if "png" in content_type:
                        ext = ".png"

                    # Создаем временный файл
                    fd, temp_path = tempfile.mkstemp(suffix=ext)
                    with os.fdopen(fd, "wb") as tmp:
                        tmp.write(photo_response.content)

                    temp_files.append(temp_path)
                    logging.info(
                        f"Создан временный файл для фотографии {i+1} квартиры {apartment_id}: {temp_path}"
                    )
                except Exception as e:
                    logging.error(
                        f"Ошибка при создании временного файла для фотографии {i+1} квартиры {apartment_id}: {e}"
                    )

            return temp_files
        except Exception as e:
            logging.error(
                f"Ошибка при получении фотографий для квартиры {apartment_id}: {e}"
            )
            return []

    def get_telegram_apartment_photos(
        self, apartment_id: int, max_photos: int = 3
    ) -> List[str]:
        """
        Получает фотографии квартиры из Telegram через API скрапера

        Args:
            apartment_id (int): ID квартиры из Telegram
            max_photos (int): Максимальное количество фотографий для возврата

        Returns:
            List[str]: Список путей к временным файлам с фотографиями
        """
        try:
            # Запрашиваем фотографии через API
            response = requests.get(
                f"{SCRAPER_SERVICE_URL}/telegram/apartments/{apartment_id}/photos",
                params={"max_photos": max_photos},
            )

            if not response.ok:
                logging.error(
                    f"Не удалось получить фотографии для Telegram квартиры {apartment_id}. Код статуса: {response.status_code}"
                )
                return []

            photos_data = response.json()
            temp_files = []

            # Создаем временные файлы для каждой фотографии
            for i, photo in enumerate(photos_data):
                try:
                    # Получаем бинарные данные фотографии
                    photo_response = requests.get(
                        f"{SCRAPER_SERVICE_URL}/telegram/photos/{photo['id']}"
                    )

                    if not photo_response.ok:
                        continue

                    # Определяем расширение файла
                    content_type = photo_response.headers.get(
                        "Content-Type", "image/jpeg"
                    )
                    ext = ".jpg"
                    if "png" in content_type:
                        ext = ".png"

                    # Создаем временный файл
                    fd, temp_path = tempfile.mkstemp(suffix=ext)
                    with os.fdopen(fd, "wb") as tmp:
                        tmp.write(photo_response.content)

                    temp_files.append(temp_path)
                    logging.info(
                        f"Создан временный файл для фотографии {i+1} Telegram квартиры {apartment_id}: {temp_path}"
                    )
                except Exception as e:
                    logging.error(
                        f"Ошибка при создании временного файла для фотографии {i+1} Telegram квартиры {apartment_id}: {e}"
                    )

            return temp_files
        except Exception as e:
            logging.error(
                f"Ошибка при получении фотографий для Telegram квартиры {apartment_id}: {e}"
            )
            return []

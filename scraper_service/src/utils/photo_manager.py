import logging
from typing import List, Tuple

import requests
from sqlalchemy.orm import Session

from src.database import ApartmentPhoto
from src.env import SKIPPED_PHOTO_INDEXES


class PhotoManager:
    """Менеджер для работы с фотографиями квартир"""

    def __init__(self):
        """
        Инициализация менеджера фотографий
        """
        self.SKIPPED_PHOTO_INDEXES = SKIPPED_PHOTO_INDEXES

    def download_apartment_photos(
        self,
        session: Session,
        apartment_id: int,
        photo_urls: List[str],
        max_photos: int = 3,
    ) -> List[int]:
        """
        Загружает фотографии квартиры и сохраняет их в базу данных

        Args:
            session (Session): Сессия SQLAlchemy
            apartment_id (int): ID квартиры
            photo_urls (List[str]): Список URL фотографий
            max_photos (int): Максимальное количество фотографий для загрузки

        Returns:
            List[int]: Список ID сохраненных фотографий
        """
        saved_photo_ids = []

        photos = (
            session.query(ApartmentPhoto).all()
        )

        photo_data = dict()
        for photo in photos:
            photo_data_tmp = photo_data.get(photo.apartment_id, [])
            photo_data_tmp.append(photo.order)
            photo_data[photo.apartment_id] = photo_data_tmp

        skip_index = 0
        for i, url in enumerate(photo_urls[:max_photos]):
            try:
                response = requests.get(url, timeout=10)
                if response.ok:
                    if i in self.SKIPPED_PHOTO_INDEXES:
                        continue

                    # Определяем тип контента из заголовков или используем значение по умолчанию
                    content_type = response.headers.get("Content-Type", "image/jpeg")

                    photo_indexes = photo_data.get(apartment_id)
                    if photo_indexes and i in photo_indexes:
                        skip_index += 1
                        continue

                    # Создаем новую запись фотографии
                    photo = ApartmentPhoto(
                        apartment_id=apartment_id,
                        photo_data=response.content,
                        content_type=content_type,
                        order=i,
                    )

                    session.add(photo)
                    session.flush()  # Чтобы получить ID

                    saved_photo_ids.append(photo.id)
                    logging.info(
                        f"Загружена фотография {i+1} для квартиры {apartment_id}"
                    )
                else:
                    logging.error(
                        f"Не удалось загрузить фотографию {i+1} для квартиры {apartment_id}. Код статуса: {response.status_code}"
                    )
            except Exception as e:
                logging.error(
                    f"Ошибка при загрузке фотографии {i+1} для квартиры {apartment_id}: {e}"
                )

        logging.debug(f"Скипнул добавление {skip_index} изображений при парсинге.")
        return saved_photo_ids

    def get_apartment_photos(
        self, session: Session, apartment_id: int, max_photos: int = 3
    ) -> List[Tuple[bytes, str]]:
        """
        Получает фотографии квартиры из базы данных

        Args:
            session (Session): Сессия SQLAlchemy
            apartment_id (int): ID квартиры
            max_photos (int): Максимальное количество фотографий для возврата

        Returns:
            List[Tuple[bytes, str]]: Список кортежей (данные фотографии, тип контента)
        """
        photos = (
            session.query(ApartmentPhoto)
            .filter(ApartmentPhoto.apartment_id == apartment_id)
            .order_by(ApartmentPhoto.order)
            .limit(max_photos)
            .all()
        )

        return [(photo.photo_data, photo.content_type) for photo in photos]

    def delete_apartment_photos(self, session: Session, apartment_id: int) -> None:
        """
        Удаляет все фотографии квартиры из базы данных

        Args:
            session (Session): Сессия SQLAlchemy
            apartment_id (int): ID квартиры
        """
        try:
            session.query(ApartmentPhoto).filter(
                ApartmentPhoto.apartment_id == apartment_id
            ).delete()
            logging.info(f"Удалены фотографии для квартиры {apartment_id}")
        except Exception as e:
            logging.error(
                f"Ошибка при удалении фотографий для квартиры {apartment_id}: {e}"
            )

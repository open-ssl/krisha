import logging
import random
import time
import typing
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    create_engine,
    true,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

from src.env import DATABASE_URL
from src.utils.rental_types import RentalTypes


load_dotenv()

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")


# Функция для создания подключения к базе данных с повторными попытками
def create_db_engine(url, max_retries=5, initial_backoff=1, max_backoff=30):
    """
    Создает подключение к базе данных с механизмом повторных попыток

    Args:
        url (str): URL подключения к базе данных
        max_retries (int): Максимальное количество попыток
        initial_backoff (int): Начальная задержка в секундах
        max_backoff (int): Максимальная задержка в секундах

    Returns:
        Engine: Объект подключения к базе данных

    Raises:
        Exception: Если не удалось подключиться после всех попыток
    """
    for attempt in range(max_retries):
        try:
            return create_engine(url)
        except OperationalError as e:
            if (
                "recovery mode" in str(e).lower()
                or "the database system is starting up" in str(e).lower()
            ):
                if attempt < max_retries - 1:
                    # Экспоненциальная задержка с случайным компонентом
                    backoff = min(max_backoff, initial_backoff * (2**attempt))
                    sleep_time = backoff + random.uniform(0, 1)
                    logging.warning(
                        f"Database in recovery mode. Retrying in {sleep_time:.2f} seconds... (Attempt {attempt+1}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                else:
                    logging.error(
                        f"Failed to connect to database after {max_retries} attempts"
                    )
                    raise
            else:
                raise
    raise Exception("Failed to connect to database after multiple attempts")


try:
    engine = create_db_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logging.error(f"Failed to initialize database connection: {e}")
    # Создаем заглушку для сессии в случае ошибки
    engine = None
    SessionLocal = None

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class ApartmentPhoto(Base):
    """Модель для хранения фотографий квартир"""

    __tablename__ = "apartment_photos"

    id = Column(Integer, primary_key=True)
    apartment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("apartments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    photo_data = Column(LargeBinary, nullable=False)
    content_type = Column(String, nullable=False, default="image/jpeg")
    order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Отношение с моделью квартиры
    apartment = relationship("Apartment", back_populates="photos")


class Apartment(Base):
    """Model for storing apartment listings"""

    __tablename__ = "apartments"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=False)
    price = Column(Float)
    rooms = Column(Integer)
    city = Column(String)
    square = Column(Float)
    district = Column(String, nullable=True)
    street = Column(String, nullable=True)
    complex_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    photos = relationship("ApartmentPhoto", back_populates="apartment")

    def to_dict(self) -> Dict:
        """Convert apartment to dictionary"""
        return {
            "id": self.id,
            "url": self.url,
            "price": self.price,
            "rooms": self.rooms,
            "city": self.city,
            "square": self.square,
            "district": self.district,
            "street": self.street,
            "complex_name": self.complex_name,
        }


class User(Base):
    """Model for storing user information"""

    __tablename__ = "users"

    id = Column(sa.BigInteger, primary_key=True)  # Telegram user ID
    is_active = Column(Boolean, default=True)  # Флаг активности пользователя
    filter_type = Column(String, nullable=True)  # Тип установленного фильтра
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    # Отношения с таблицами фильтров
    full_apartment_filter = relationship(
        "FullApartmentFilter",
        back_populates="user",
    )
    room_sharing_filter = relationship(
        "RoomSharingFilter",
        back_populates="user",
    )


# Базовый класс для фильтров (не создает таблицу)
class BaseFilter:
    """Base model for filter fields"""

    city = Column(String, nullable=True)
    rooms = Column(ARRAY(Integer), nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    min_square = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FullApartmentFilter(Base, BaseFilter):
    """Model for storing full apartment filters"""

    __tablename__ = "full_apartment_filters"

    id = Column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Отношение с моделью пользователя
    user = relationship("User", back_populates="full_apartment_filter")


class RoomSharingFilter(Base, BaseFilter):
    """Model for storing room sharing filters"""

    __tablename__ = "room_sharing_filters"

    id = Column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gender = Column(String, nullable=True)
    roommate_preference = Column(String, nullable=True)

    # Отношение с моделью пользователя
    user = relationship("User", back_populates="room_sharing_filter")


class CommunityFullApartmentFilter(Base, BaseFilter):
    """Model for community full apartment filters"""

    __tablename__ = "community_full_apartment_filters"

    id = Column(Integer, primary_key=True)
    community_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        index=True,
    )


class CommunitySharingFilter(Base, BaseFilter):
    """Model for community room sharing filters"""

    __tablename__ = "community_sharing_filters"

    id = Column(Integer, primary_key=True)
    community_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        index=True,
    )
    gender = Column(String, nullable=True)
    roommate_preference = Column(String, nullable=True)


# Оставляем старую модель для обратной совместимости и миграций
class UserFilter(Base):
    """Model for storing user filters (legacy)"""

    __tablename__ = "user_filters"

    id = Column(Integer, primary_key=True)
    # user_id = Column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    city = Column(String, nullable=True)
    rooms = Column(ARRAY(Integer), nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    min_square = Column(Float, nullable=True)
    rental_type = Column(
        String, nullable=True
    )  # Тип съёма: full_apartment или room_sharing
    gender = Column(String, nullable=True)  # Пол пользователя: male или female
    roommate_preference = Column(
        String, nullable=True
    )  # Предпочтения по соседям: prefer_male, prefer_female, no_preference
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSeenApartment(Base):
    """Model for storing seen apartments by user"""

    __tablename__ = "user_seen_apartments"

    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    apartment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("apartments.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    apartment_type = Column(String, nullable=True)
    seen_at = Column(DateTime, default=datetime.utcnow)


class CommunitySeenApartment(Base):
    """Model for storing seen apartments by community"""

    __tablename__ = "community_seen_apartments"

    community_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        index=True,
    )
    apartment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("apartments.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    apartment_type = Column(String, nullable=True)
    seen_at = Column(DateTime, default=datetime.utcnow)


class TelegramApartment(Base):
    """
    Модель для хранения объявлений об аренде квартир из Telegram.

    Attributes:
        id (int): Уникальный идентификатор записи
        message_id (int): ID сообщения в Telegram
        channel_username (str): Имя канала/группы, из которого получено сообщение
        is_offer (bool): Является ли объявлением о сдаче в аренду
        is_roommate_offer (bool): Является ли объявлением о поиске соседа
        is_rental_offer (bool): Является ли объявлением о долгосрочной аренде
        monthly_price (str): Цена аренды
        preferred_gender (str): Предпочтительный пол для соседа
        location (str): Местоположение квартиры
        contact (str): Контактная информация
        text (str): Полный текст объявления
        created_at (datetime): Дата создания записи
        photos (list): Список фотографий объявления
    """

    __tablename__ = "telegram_apartments"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    channel_username = Column(String)
    is_offer = Column(Boolean, default=False)
    is_roommate_offer = Column(Boolean, default=False)
    is_rental_offer = Column(Boolean, default=False)
    monthly_price = Column(Integer)
    preferred_gender = Column(String)
    location = Column(String)
    contact = Column(String)
    city = Column(String, index=True)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    photos = relationship(
        "TelegramApartmentPhoto",
        back_populates="apartment",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> Dict:
        """Convert apartment to dictionary"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "channel_username": self.channel_username,
            "is_offer": self.is_offer,
            "is_roommate_offer": self.is_roommate_offer,
            "is_rental_offer": self.is_rental_offer,
            "monthly_price": self.monthly_price,
            "preferred_gender": self.preferred_gender,
            "location": self.location,
            "contact": self.contact,
            "city": self.city,
            "text": self.text,
        }


class TelegramApartmentPhoto(Base):
    """
    Модель для хранения фотографий квартир из Telegram.

    Attributes:
        id (uuid4): Уникальный идентификатор фотографии в формате UUID
        apartment_id (int): Идентификатор квартиры, к которой относится фотография
        photo_data (bytes): Данные фотографии в бинарном формате
        created_at (datetime): Дата и время создания записи
    """

    __tablename__ = "telegram_apartment_photos"

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    apartment_id = Column(
        Integer,
        ForeignKey("telegram_apartments.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Отношение к квартире
    apartment = relationship("TelegramApartment", back_populates="photos")


class UserSeenTelegramApartment(Base):
    """Model for storing seen Telegram apartments by user"""

    __tablename__ = "user_seen_telegram_apartments"

    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    apartment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("telegram_apartments.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    seen_at = Column(DateTime, default=datetime.utcnow)

    # Определяем составной первичный ключ
    __table_args__ = (sa.PrimaryKeyConstraint("user_id", "apartment_id"),)


class CommunitySeenTelegramApartment(Base):
    """Model for storing seen Telegram apartments by community"""

    __tablename__ = "community_seen_telegram_apartments"

    community_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        index=True,
    )
    apartment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("telegram_apartments.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    seen_at = Column(DateTime, default=datetime.utcnow)

    # Определяем составной первичный ключ
    __table_args__ = (sa.PrimaryKeyConstraint("community_id", "apartment_id"),)


def save_apartment(
    url: str,
    price: float,
    square: str,
    rooms: int,
    city: str,
    district: str = None,
    street: str = None,
    complex_name: str = None,
    listing_date: datetime = None,
) -> typing.Any:
    """
    Save apartment to database

    Args:
        url (str): URL of the apartment listing
        price (float): Price of the apartment
        square (str): Square footage of the apartment
        rooms (int): Number of rooms
        city (str): City name
        district (str, optional): District name. Defaults to None.
        street (str, optional): Street name. Defaults to None.
        complex_name (str, optional): Complex name. Defaults to None.
        listing_date (datetime, optional): Listing date. Defaults to None.

    Returns:
        Optional[int]: ID of the saved apartment or None if failed
    """
    session = SessionLocal()
    try:
        # Проверяем, существует ли уже такая квартира
        existing = session.query(Apartment).filter(Apartment.url == url).first()
        if existing:
            logging.debug(f"Apartment already exists: {url}")
            session.close()
            return existing.id

        # Создаем новую запись
        apartment = Apartment(
            url=url,
            price=price,
            square=square,
            rooms=rooms,
            city=city,
            district=district,
            street=street,
            complex_name=complex_name,
            created_at=listing_date if listing_date else datetime.utcnow(),
        )
        session.add(apartment)
        session.commit()
        apartment_id = apartment.id
        session.close()
        return apartment_id
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving apartment: {e}")
        session.close()
        return None


def get_apartments(
    city: str = None,
    rooms: list = None,
    min_price: float = None,
    max_price: float = None,
    min_square: float = None,
) -> List[Dict]:
    """
    Get apartments matching criteria

    Args:
        city (str, optional): City filter
        rooms (list, optional): List of acceptable room numbers
        min_price (float, optional): Minimum price
        max_price (float, optional): Maximum price
        min_square (float, optional): Minimum square


    Returns:
        List[Dict]: List of matching apartments
    """
    session = SessionLocal()
    query = session.query(Apartment)

    if city:
        query = query.filter(Apartment.city == city)
    if min_price:
        query = query.filter(Apartment.price >= min_price)
    if max_price:
        query = query.filter(Apartment.price <= max_price)
    if rooms:
        query = query.filter(Apartment.rooms.in_(rooms))
    if min_square:
        query = query.filter(Apartment.square >= min_square)

    # Преобразуем объекты Apartment в словари
    return [apartment.to_dict() for apartment in query.all()]


def cleanup_old_entries() -> None:
    """Remove entries older than 3 days and their photos"""
    session = SessionLocal()
    try:
        three_days_ago = datetime.utcnow() - timedelta(days=3)

        # Подсчитываем количество записей для логирования
        apartments_count = (
            session.query(Apartment)
            .filter(Apartment.created_at < three_days_ago)
            .count()
        )
        telegram_apartments_count = (
            session.query(TelegramApartment)
            .filter(TelegramApartment.created_at < three_days_ago)
            .count()
        )

        logging.info(
            f"Cleaning up old entries: {apartments_count} apartments and {telegram_apartments_count} telegram apartments older than 3 days"
        )

        # Удаляем старые записи из таблицы user_seen_apartments
        session.query(UserSeenApartment).filter(
            UserSeenApartment.seen_at < three_days_ago
        ).delete(synchronize_session=False)

        # Удаляем старые записи из таблицы user_seen_telegram_apartments
        session.query(UserSeenTelegramApartment).filter(
            UserSeenTelegramApartment.seen_at < three_days_ago
        ).delete(synchronize_session=False)

        # Удаляем старые квартиры из таблицы apartments
        # Фотографии будут удалены автоматически благодаря каскадному удалению (CASCADE)
        session.query(Apartment).filter(Apartment.created_at < three_days_ago).delete(
            synchronize_session=False
        )

        # Удаляем старые квартиры из таблицы telegram_apartments
        # Фотографии будут удалены автоматически благодаря каскадному удалению (CASCADE)
        session.query(TelegramApartment).filter(
            TelegramApartment.created_at < three_days_ago
        ).delete(synchronize_session=False)

        # Фиксируем изменения
        session.commit()

        logging.info(f"Удалено {apartments_count} устаревших full объявлений")
        logging.info(
            f"Удалено {telegram_apartments_count} устаревших sharing объявлений"
        )
    except Exception as e:
        session.rollback()
        logging.error(f"Ошибка при old entries: {e}")
    finally:
        session.close()


def create_or_update_user(
    user_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_active: bool = True,
    filter_type: Optional[str] = None,
) -> None:
    """
    Create or update user in database

    Args:
        user_id (int): Telegram user ID
        first_name (str, optional): User's first name
        last_name (str, optional): User's last name
        is_active (bool): User active status
        filter_type (str, optional): Type of filter set by user
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = is_active
            user.updated_at = datetime.utcnow()
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if filter_type is not None:
                user.filter_type = filter_type
        else:
            user = User(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                filter_type=filter_type,
            )
            session.add(user)
        session.commit()
    except Exception as e:
        logging.error(f"Error creating/updating user: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_active_users() -> List[int]:
    """
    Get list of active user IDs

    Returns:
        List[int]: List of active user IDs
    """
    session = SessionLocal()
    try:
        users = session.query(User.id).filter(User.is_active == sa.true()).all()
        return [user.id for user in users]
    finally:
        session.close()


def is_user_active(user_id: int) -> bool:
    """
    Check if user is active

    Args:
        user_id (int): Telegram user ID

    Returns:
        bool: True if user is active
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        return user.is_active if user else False
    finally:
        session.close()


def save_user_filter(
    user_id: int,
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_square: Optional[float] = None,
    rooms: Optional[List[int]] = None,
    rental_type: Optional[str] = None,
    gender: Optional[str] = None,
    roommate_preference: Optional[str] = None,
) -> None:
    """
    Save user filter to database using the new structure

    Args:
        user_id (int): Telegram user ID
        city (Optional[str], optional): City name. Defaults to None.
        min_price (Optional[float], optional): Minimum price. Defaults to None.
        max_price (Optional[float], optional): Maximum price. Defaults to None.
        min_square (Optional[float], optional): Minimum square. Defaults to None.
        rooms (Optional[List[int]], optional): List of room numbers. Defaults to None.
        rental_type (Optional[str], optional): Rental type. Defaults to None.
        gender (Optional[str], optional): User's gender. Defaults to None.
        roommate_preference (Optional[str], optional): Roommate preference. Defaults to None.
    """
    session = SessionLocal()
    try:
        # Сначала получаем или создаем пользователя
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id)
            session.add(user)
            session.flush()

        # Обновляем тип фильтра пользователя
        user.filter_type = rental_type

        # В зависимости от типа фильтра, сохраняем в соответствующую таблицу
        if rental_type == RentalTypes.FULL_APARTMENT:
            # Удаляем старый фильтр подселения, если он есть
            if user.room_sharing_filter:
                session.delete(user.room_sharing_filter)

            # Создаем или обновляем фильтр жилья целиком
            if user.full_apartment_filter:
                filter_obj = user.full_apartment_filter
                filter_obj.city = city
                filter_obj.min_price = min_price
                filter_obj.max_price = max_price
                filter_obj.min_square = min_square
                filter_obj.rooms = rooms
                filter_obj.updated_at = datetime.utcnow()

        elif rental_type == RentalTypes.ROOM_SHARING:
            # Удаляем старый фильтр жилья целиком, если он есть
            if user.full_apartment_filter:
                session.delete(user.full_apartment_filter)

            # Создаем или обновляем фильтр подселения
            if user.room_sharing_filter:
                filter_obj = user.room_sharing_filter
                filter_obj.city = city
                filter_obj.min_price = min_price
                filter_obj.max_price = max_price
                filter_obj.min_square = min_square
                filter_obj.rooms = rooms
                filter_obj.gender = gender
                filter_obj.roommate_preference = roommate_preference
                filter_obj.updated_at = datetime.utcnow()

        # Для обратной совместимости также сохраняем в старую таблицу
        legacy_filter = (
            session.query(UserFilter).filter(UserFilter.user_id == user_id).first()
        )
        if legacy_filter:
            legacy_filter.city = city
            legacy_filter.min_price = min_price
            legacy_filter.max_price = max_price
            legacy_filter.min_square = min_square
            legacy_filter.rooms = rooms
            legacy_filter.rental_type = rental_type
            legacy_filter.gender = gender
            legacy_filter.roommate_preference = roommate_preference
            legacy_filter.updated_at = datetime.utcnow()
        else:
            legacy_filter = UserFilter(
                user_id=user_id,
                city=city,
                min_price=min_price,
                max_price=max_price,
                min_square=min_square,
                rooms=rooms,
                rental_type=rental_type,
                gender=gender,
                roommate_preference=roommate_preference,
            )
            session.add(legacy_filter)

        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving user filter: {e}")
        raise
    finally:
        session.close()


def get_user_filter(user_id: int) -> Optional[Dict]:
    """
    Get user filter from database using the new structure

    Args:
        user_id (int): Telegram user ID

    Returns:
        Optional[Dict]: User filter or None if not found
    """
    session = SessionLocal()
    try:
        # Получаем пользователя
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # Определяем тип фильтра
        filter_type = user.filter_type

        # В зависимости от типа фильтра, получаем из соответствующей таблицы
        if filter_type == RentalTypes.FULL_APARTMENT:
            filter_obj = user.full_apartment_filter
            if filter_obj:
                return {
                    "user_id": user_id,
                    "city": filter_obj.city,
                    "min_price": filter_obj.min_price,
                    "max_price": filter_obj.max_price,
                    "min_square": filter_obj.min_square,
                    "rooms": filter_obj.rooms,
                    "rental_type": RentalTypes.FULL_APARTMENT,
                    "gender": None,
                    "roommate_preference": None,
                }
        elif filter_type == RentalTypes.ROOM_SHARING:
            filter_obj = user.room_sharing_filter
            if filter_obj:
                return {
                    "user_id": user_id,
                    "city": filter_obj.city,
                    "min_price": filter_obj.min_price,
                    "max_price": filter_obj.max_price,
                    "min_square": filter_obj.min_square,
                    "rooms": filter_obj.rooms,
                    "rental_type": RentalTypes.ROOM_SHARING,
                    "gender": filter_obj.gender,
                    "roommate_preference": filter_obj.roommate_preference,
                }

        # Если не нашли в новых таблицах, пробуем получить из старой для обратной совместимости
        legacy_filter = (
            session.query(UserFilter).filter(UserFilter.user_id == user_id).first()
        )
        if legacy_filter:
            return {
                "user_id": user_id,
                "city": legacy_filter.city,
                "min_price": legacy_filter.min_price,
                "max_price": legacy_filter.max_price,
                "min_square": legacy_filter.min_square,
                "rooms": legacy_filter.rooms,
                "rental_type": legacy_filter.rental_type,
                "gender": legacy_filter.gender,
                "roommate_preference": legacy_filter.roommate_preference,
            }

        return None
    finally:
        session.close()


def mark_apartment_as_seen(
    user_id: int, apartment_id: int, apartment_type: str
) -> None:
    """Mark apartment as seen by user"""
    session = SessionLocal()
    try:
        seen = UserSeenApartment(
            user_id=user_id, apartment_id=apartment_id, apartment_type=apartment_type
        )
        session.add(seen)
        session.commit()
    except:
        session.rollback()
    finally:
        session.close()


def mark_full_apartments_as_seen_bulk(
    user_id: int, apartment_ids: List[int], apartment_type: str
) -> None:
    """
    Mark multiple apartments as seen by user in a single database session

    Args:
        user_id (int): The ID of the user who has seen the apartments
        apartment_ids (List[int]): List of apartment IDs that the user has seen
        apartment_type (str): Apartment type
    """
    if not apartment_ids:
        return  # Ничего не делаем, если список пустой

    session = SessionLocal()
    try:
        # Создаем список объектов UserSeenApartment для массовой вставки
        seen_apartments = [
            UserSeenApartment(
                user_id=user_id, apartment_id=apt_id, apartment_type=apartment_type
            )
            for apt_id in apartment_ids
        ]

        # Добавляем все записи в сессию
        session.bulk_save_objects(seen_apartments)
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to mark apartments as seen in bulk: {e}")
    finally:
        session.close()


def mark_community_full_apartments_as_seen_bulk(
    community_id: int, apartment_ids: List[int], apartment_type: str
) -> None:
    """
    Mark multiple apartments as seen by user in a single database session

    Args:
        community_id (int): The ID of the community who has seen the apartments
        apartment_ids (List[int]): List of apartment IDs that the user has seen
        apartment_type (str): Apartment type
    """
    if not apartment_ids:
        return  # Ничего не делаем, если список пустой

    session = SessionLocal()
    try:
        # Создаем список объектов UserSeenApartment для массовой вставки
        seen_apartments = [
            CommunitySeenApartment(
                community_id=community_id,
                apartment_id=apt_id,
                apartment_type=apartment_type,
            )
            for apt_id in apartment_ids
        ]

        # Добавляем все записи в сессию
        session.bulk_save_objects(seen_apartments)
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to mark apartments as seen in bulk: {e}")
    finally:
        session.close()


def mark_telegram_apartments_as_seen_bulk(
    user_id: int, apartment_ids: List[int]
) -> None:
    """
    Mark multiple Telegram apartments as seen by user in a single database session

    Args:
        user_id (int): The ID of the user who has seen the apartments
        apartment_ids (List[int]): List of Telegram apartment IDs that the user has seen
    """
    if not apartment_ids:
        return  # Ничего не делаем, если список пустой

    session = SessionLocal()
    try:
        # Создаем список объектов UserSeenTelegramApartment для массовой вставки
        seen_apartments = [
            UserSeenTelegramApartment(user_id=user_id, apartment_id=apt_id)
            for apt_id in apartment_ids
        ]

        # Добавляем все записи в сессию
        session.bulk_save_objects(seen_apartments)
        session.commit()
        logging.info(
            f"Marked {len(apartment_ids)} Telegram apartments as seen for user {user_id}"
        )
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to mark Telegram apartments as seen in bulk: {e}")
    finally:
        session.close()


def mark_community_telegram_apartments_as_seen_bulk(
    community_id: int, apartment_ids: List[int]
) -> None:
    """
    Mark multiple Telegram apartments as seen by user in a single database session

    Args:
        community_id (int): The ID of the community who has seen the apartments
        apartment_ids (List[int]): List of Telegram apartment IDs that the user has seen
    """
    if not apartment_ids:
        return  # Ничего не делаем, если список пустой

    session = SessionLocal()
    try:
        # Создаем список объектов UserSeenTelegramApartment для массовой вставки
        seen_apartments = [
            CommunitySeenTelegramApartment(
                community_id=community_id, apartment_id=apt_id
            )
            for apt_id in apartment_ids
        ]

        # Добавляем все записи в сессию
        session.bulk_save_objects(seen_apartments)
        session.commit()
        logging.info(
            f"Marked {len(apartment_ids)} Telegram apartments as seen for community {community_id}"
        )
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to mark Telegram apartments as seen in bulk: {e}")
    finally:
        session.close()


def get_unseen_full_apartments(user_id: int, **filters) -> List[Dict]:
    """
    Get apartments that user hasn't seen yet

    Args:
        user_id (int): User ID to check against
        **filters: Additional filters for apartments (city, min_price, max_price, min_square, rooms)

    Returns:
        List[Dict]: List of apartments that the user hasn't seen
    """
    session = SessionLocal()
    try:
        # Подзапрос для получения ID квартир, которые пользователь уже видел
        seen_apartment_ids = (
            session.query(UserSeenApartment.apartment_id)
            .filter(
                UserSeenApartment.user_id == user_id,
                UserSeenApartment.apartment_type == RentalTypes.FULL_APARTMENT,
            )
            .subquery()
        )

        # Основной запрос: выбираем квартиры, ID которых нет в подзапросе
        query = session.query(Apartment).filter(Apartment.id.notin_(seen_apartment_ids))

        # Применяем дополнительные фильтры, если они указаны
        if filters.get("city"):
            query = query.filter(Apartment.city == filters["city"])
        if filters.get("min_price"):
            query = query.filter(Apartment.price >= filters["min_price"])
        if filters.get("max_price"):
            query = query.filter(Apartment.price <= filters["max_price"])
        if filters.get("min_square"):
            query = query.filter(Apartment.square >= filters["min_square"])
        if filters.get("rooms"):
            query = query.filter(Apartment.rooms.in_(filters["rooms"]))

        # Преобразуем объекты Apartment в словари
        return [apartment.to_dict() for apartment in query.all()]
    finally:
        session.close()


def get_community_unseen_full_apartments(community_id: int, **filters) -> List[Dict]:
    """
    Get apartments that user hasn't seen yet

    Args:
        community_id (int): Community ID to check against
        **filters: Additional filters for apartments (city, min_price, max_price, min_square, rooms)

    Returns:
        List[Dict]: List of apartments that the user hasn't seen
    """
    session = SessionLocal()
    try:
        # Подзапрос для получения ID квартир, которые пользователь уже видел
        seen_apartment_ids = (
            session.query(CommunitySeenApartment.apartment_id)
            .filter(
                CommunitySeenApartment.community_id == community_id,
                UserSeenApartment.apartment_type == RentalTypes.FULL_APARTMENT,
            )
            .subquery()
        )

        # Основной запрос: выбираем квартиры, ID которых нет в подзапросе
        query = session.query(Apartment).filter(Apartment.id.notin_(seen_apartment_ids))

        # Применяем дополнительные фильтры, если они указаны
        if filters.get("city"):
            query = query.filter(Apartment.city == filters["city"])
        if filters.get("min_price"):
            query = query.filter(Apartment.price >= filters["min_price"])
        if filters.get("max_price"):
            query = query.filter(Apartment.price <= filters["max_price"])
        if filters.get("min_square"):
            query = query.filter(Apartment.square >= filters["min_square"])
        if filters.get("rooms"):
            query = query.filter(Apartment.rooms.in_(filters["rooms"]))

        # Преобразуем объекты Apartment в словари
        return [apartment.to_dict() for apartment in query.all()]
    finally:
        session.close()


def get_unseen_sharing_apartments(user_id: int, **filters) -> List[Dict]:
    """
    Get apartments that user hasn't seen yet

    Args:
        user_id (int): User ID to check against
        **filters: Additional filters for apartments (city, min_price, max_price, min_square, rooms)

    Returns:
        List[Dict]: List of apartments that the user hasn't seen
    """
    session = SessionLocal()
    try:
        # Подзапрос для получения ID квартир, которые пользователь уже видел
        seen_apartment_ids = (
            session.query(UserSeenTelegramApartment.apartment_id)
            .filter(
                UserSeenTelegramApartment.user_id == user_id,
            )
            .scalar_subquery()
        )

        # Основной запрос: выбираем квартиры, ID которых нет в подзапросе
        query = session.query(TelegramApartment).filter(
            TelegramApartment.is_roommate_offer == true(),
            TelegramApartment.id.notin_(seen_apartment_ids),
        )

        # Применяем дополнительные фильтры, если они указаны
        if filters.get("city"):
            query = query.filter(TelegramApartment.city == filters["city"])
        if filters.get("max_price"):
            query = query.filter(
                TelegramApartment.monthly_price <= int(filters["max_price"])
            )

        accepted_genders = ["both", "no"]
        if filters.get("gender") == "male":
            accepted_genders.append("boy")
        elif filters.get("gender") == "female":
            accepted_genders.append("girl")

        query = query.filter(TelegramApartment.preferred_gender.in_(accepted_genders))

        # Преобразуем объекты Apartment в словари
        return [apartment.to_dict() for apartment in query.all()]
    finally:
        session.close()


def get_unseen_community_sharing_apartments(community_id: int, **filters) -> List[Dict]:
    """
    Get apartments that community hasn't seen yet

    Args:
        community_id (int): Community ID to check against
        **filters: Additional filters for apartments (city, min_price, max_price, min_square, rooms)

    Returns:
        List[Dict]: List of apartments that the user hasn't seen
    """
    session = SessionLocal()
    try:
        # Подзапрос для получения ID квартир, которые пользователь уже видел
        seen_apartment_ids = (
            session.query(CommunitySeenTelegramApartment.apartment_id)
            .filter(
                CommunitySeenTelegramApartment.community_id == community_id,
            )
            .scalar_subquery()
        )

        # Основной запрос: выбираем квартиры, ID которых нет в подзапросе
        query = session.query(TelegramApartment).filter(
            TelegramApartment.is_roommate_offer == true(),
            TelegramApartment.id.notin_(seen_apartment_ids),
        )

        # Применяем дополнительные фильтры, если они указаны
        if filters.get("city"):
            query = query.filter(TelegramApartment.city == filters["city"])
        if filters.get("max_price"):
            query = query.filter(
                TelegramApartment.monthly_price <= int(filters["max_price"])
            )

        if filters.get("min_price"):
            query = query.filter(
                TelegramApartment.monthly_price >= int(filters["min_price"])
            )

        accepted_genders = ["both", "no"]
        if filters.get("gender") == "male":
            accepted_genders.append("boy")
        elif filters.get("gender") == "female":
            accepted_genders.append("girl")

        query = query.filter(TelegramApartment.preferred_gender.in_(accepted_genders))

        # Преобразуем объекты Apartment в словари
        return [apartment.to_dict() for apartment in query.all()]
    finally:
        session.close()


def get_all_user_filters() -> List[Dict]:
    """
    Get all user filters using the new structure

    Returns:
        List[Dict]: List of user filters with all fields
    """
    session = SessionLocal()
    try:
        # Получаем всех активных пользователей
        active_users = session.query(User).filter(User.is_active == sa.true()).all()

        filters = []

        for user in active_users:
            # Пропускаем пользователей без фильтра
            if not user.filter_type:
                continue

            # В зависимости от типа фильтра, получаем из соответствующей таблицы
            if (
                user.filter_type == RentalTypes.FULL_APARTMENT
                and user.full_apartment_filter
            ):
                filter_obj = user.full_apartment_filter
                filters.append(
                    {
                        "user_id": user.id,
                        "city": filter_obj.city,
                        "min_price": filter_obj.min_price,
                        "max_price": filter_obj.max_price,
                        "min_square": filter_obj.min_square,
                        "rooms": filter_obj.rooms,
                        "rental_type": RentalTypes.FULL_APARTMENT,
                        "gender": None,
                        "roommate_preference": None,
                    }
                )
            elif (
                user.filter_type == RentalTypes.ROOM_SHARING
                and user.room_sharing_filter
            ):
                filter_obj = user.room_sharing_filter
                filters.append(
                    {
                        "user_id": user.id,
                        "city": filter_obj.city,
                        "max_price": filter_obj.max_price,
                        "min_price": filter_obj.min_price,
                        "rental_type": RentalTypes.ROOM_SHARING,
                        "gender": filter_obj.gender,
                        "roommate_preference": filter_obj.roommate_preference,
                    }
                )

        # Если список пустой, пробуем получить из старой таблицы для обратной совместимости
        if not filters:
            legacy_filters = (
                session.query(UserFilter)
                .join(User)
                .filter(User.is_active == sa.true())
                .all()
            )

            filters = [
                {
                    "user_id": f.user_id,
                    "city": f.city,
                    "min_price": f.min_price,
                    "max_price": f.max_price,
                    "min_square": f.min_square,
                    "rooms": f.rooms,
                    "rental_type": f.rental_type,
                    "gender": f.gender,
                    "roommate_preference": f.roommate_preference,
                }
                for f in legacy_filters
            ]

        return filters
    finally:
        session.close()


def get_all_community_full_filters() -> List[Dict]:
    """
    Get all user filters using the new structure

    Returns:
        List[Dict]: List of user filters with all fields
    """
    session = SessionLocal()
    try:
        active_filters = session.query(CommunityFullApartmentFilter).all()

        filters = []

        for filter_obj in active_filters:
            filters.append(
                {
                    "filter_type": "community",
                    "community_id": filter_obj.community_id,
                    "city": filter_obj.city,
                    "min_price": filter_obj.min_price,
                    "max_price": filter_obj.max_price,
                    "min_square": filter_obj.min_square,
                    "rooms": filter_obj.rooms,
                    "rental_type": RentalTypes.FULL_APARTMENT,
                    "gender": None,
                    "roommate_preference": None,
                }
            )

        return filters
    finally:
        session.close()


def get_all_community_sharing_filters() -> List[Dict]:
    """
    Get all user filters using the new structure

    Returns:
        List[Dict]: List of user filters with all fields
    """
    session = SessionLocal()
    try:
        active_filters = session.query(CommunitySharingFilter).all()

        filters = []

        for filter_obj in active_filters:
            filters.append(
                {
                    "filter_type": "community",
                    "community_id": filter_obj.community_id,
                    "city": filter_obj.city,
                    "max_price": filter_obj.max_price,
                    "min_price": filter_obj.min_price,
                    "rental_type": RentalTypes.ROOM_SHARING,
                    "gender": filter_obj.gender,
                    "roommate_preference": filter_obj.roommate_preference,
                }
            )

        return filters

    finally:
        session.close()


def delete_user_filter(user_id: int) -> None:
    """
    Delete user filter from database using the new structure

    Args:
        user_id (int): Telegram user ID
    """
    session = SessionLocal()
    try:
        # Получаем пользователя
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            # Удаляем фильтры из всех таблиц
            if user.full_apartment_filter:
                session.delete(user.full_apartment_filter)

            if user.room_sharing_filter:
                session.delete(user.room_sharing_filter)

            # Сбрасываем тип фильтра
            user.filter_type = None

        # Для обратной совместимости удаляем из старой таблицы
        session.query(UserFilter).filter(UserFilter.user_id == user_id).delete()

        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error deleting user filter: {e}")
        raise
    finally:
        session.close()

from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Указываем схему для всех таблиц
metadata = MetaData(schema='rent_service')
Base = declarative_base(metadata=metadata)

class Apartment(Base):
    """Model for storing apartment listings"""
    __tablename__ = 'apartments'

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    price = Column(Float)
    rooms = Column(Integer)
    city = Column(String)
    district = Column(String, nullable=True)
    street = Column(String, nullable=True)
    complex_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    """Model for storing user information"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)  # Telegram user ID
    is_active = Column(Boolean, default=True)  # Флаг активности пользователя
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

def save_apartment(url: str, price: float, rooms: int, city: str, 
                  district: str = None, street: str = None, 
                  complex_name: str = None) -> None:
    """
    Save apartment to database
    
    Args:
        url (str): URL of the apartment listing
        price (float): Price of the apartment
        rooms (int): Number of rooms
        city (str): City where apartment is located
        district (str, optional): District name
        street (str, optional): Street name
        complex_name (str, optional): Housing complex name
    """
    session = SessionLocal()
    apartment = Apartment(
        url=url, 
        price=price, 
        rooms=rooms, 
        city=city,
        district=district,
        street=street,
        complex_name=complex_name
    )
    session.add(apartment)
    try:
        session.commit()
    except:
        session.rollback()
    finally:
        session.close()


def get_apartments(city: str = None, min_price: float = None, 
                  max_price: float = None, rooms: list = None) -> list:
    """
    Get apartments matching criteria
    
    Args:
        city (str, optional): City filter
        min_price (float, optional): Minimum price
        max_price (float, optional): Maximum price
        rooms (list, optional): List of acceptable room numbers
    
    Returns:
        list: List of matching apartments
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
        
    return query.all()

def cleanup_old_entries() -> None:
    """Remove entries older than 3 days"""
    session = SessionLocal()
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    session.query(Apartment).filter(Apartment.created_at < three_days_ago).delete()
    session.commit()
    session.close()

def create_or_update_user(user_id: int, first_name: Optional[str] = None, 
                         last_name: Optional[str] = None, is_active: bool = True) -> None:
    """
    Create or update user in database
    
    Args:
        user_id (int): Telegram user ID
        first_name (str, optional): User's first name
        last_name (str, optional): User's last name
        is_active (bool): User active status
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
        else:
            user = User(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active
            )
            session.add(user)
        session.commit()
    except Exception as e:
        print(f"Error creating/updating user: {e}")
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
        users = session.query(User.id).filter(User.is_active == True).all()
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
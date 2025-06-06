import logging
import os
import re
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from database import (
    SessionLocal,
    get_all_community_full_filters,
    get_all_community_sharing_filters,
    get_all_user_filters,
    get_community_unseen_full_apartments,
    get_unseen_community_sharing_apartments,
    get_unseen_full_apartments,
    get_unseen_sharing_apartments,
    save_apartment,
)
from notifications import NotificationManager
from proxy_manager import ProxyManager as BaseProxyManager
from utils.city_mapping import CITY_MAPPING, get_city_name
from utils.photo_manager import PhotoManager
from utils.rental_types import RentalTypes


class ProxyManager(BaseProxyManager):
    def __init__(self, cooldown_minutes: int = 1, failed_cooldown_hours: int = 2):
        super().__init__()
        self.used_proxies: dict[str, datetime] = {}  # Прокси и время их использования
        self.successful_proxies: dict[str, bool] = {}  # Прокси и их успешность
        self.failed_proxies: dict[
            str, datetime
        ] = {}  # Неудачные прокси и время их блокировки
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.failed_cooldown = timedelta(hours=failed_cooldown_hours)

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Получает прокси, сначала пытаясь использовать успешные

        Returns:
            Optional[Dict[str, str]]: Словарь с прокси или None
        """
        now = datetime.now()
        # Очищаем старые неудачные прокси
        self.failed_proxies = {
            proxy: blocked_time
            for proxy, blocked_time in self.failed_proxies.items()
            if now - blocked_time <= self.failed_cooldown
        }

        # Сначала пробуем использовать успешные прокси
        for proxy_str, is_successful in self.successful_proxies.items():
            if (
                is_successful
                and self.is_proxy_available(proxy_str)
                and proxy_str not in self.failed_proxies
            ):
                proxy = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
                self.mark_proxy_used(proxy_str)
                logging.info(f"Using successful proxy: {proxy_str}")
                return proxy

        # Если нет успешных прокси, получаем новый
        max_attempts = 5
        for _ in range(max_attempts):
            proxy = super().get_proxy()
            if proxy and isinstance(proxy, dict) and "http" in proxy:
                proxy_str = proxy["http"].replace("http://", "")
                if (
                    self.is_proxy_available(proxy_str)
                    and proxy_str not in self.failed_proxies
                ):
                    formatted_proxy = {
                        "http": f"http://{proxy_str}",
                        "https": f"http://{proxy_str}",
                    }
                    self.mark_proxy_used(proxy_str)
                    return formatted_proxy
        return None

    def is_proxy_available(self, proxy: str) -> bool:
        """
        Проверяет, можно ли использовать прокси

        Args:
            proxy: Прокси адрес

        Returns:
            bool: True если прокси можно использовать
        """
        if proxy not in self.used_proxies:
            return True

        last_used = self.used_proxies[proxy]
        time_since_use = datetime.now() - last_used
        if time_since_use <= self.cooldown:
            logging.debug(
                f"Proxy {proxy} on cooldown for {(self.cooldown - time_since_use).seconds} more seconds"
            )
            return False
        return True

    def mark_proxy_used(self, proxy: str) -> None:
        """
        Отмечает прокси как использованный

        Args:
            proxy: Прокси адрес
        """
        self.used_proxies[proxy] = datetime.now()

    def mark_proxy_success(self, proxy_str: str) -> None:
        """
        Отмечает прокси как успешный

        Args:
            proxy_str: Прокси адрес
        """
        self.successful_proxies[proxy_str] = True
        logging.info(f"Marked proxy as successful: {proxy_str}")

    def mark_proxy_failure(self, proxy_str: str) -> None:
        """
        Отмечает прокси как неуспешный и блокирует его на 2 часа

        Args:
            proxy_str: Прокси адрес
        """
        self.successful_proxies[proxy_str] = False
        self.failed_proxies[proxy_str] = datetime.now()
        logging.info(
            f"Marked proxy as failed: {proxy_str} "
            f"(blocked until {(datetime.now() + self.failed_cooldown).strftime('%H:%M:%S')})"
        )

    def clean_old_proxies(self) -> None:
        """Удаляет старые прокси из истории"""
        now = datetime.now()
        # Очищаем использованные прокси
        self.used_proxies = {
            proxy: last_used
            for proxy, last_used in self.used_proxies.items()
            if now - last_used <= self.cooldown
        }
        # Очищаем успешные прокси, которые давно не использовались
        for proxy in list(self.successful_proxies.keys()):
            if proxy not in self.used_proxies:
                del self.successful_proxies[proxy]
        # Очищаем старые неудачные прокси
        self.failed_proxies = {
            proxy: blocked_time
            for proxy, blocked_time in self.failed_proxies.items()
            if now - blocked_time <= self.failed_cooldown
        }


class KrishaScraper:
    """Scraper for krisha.kz website"""

    def __init__(self):
        self.base_url = "https://krisha.kz"
        self.proxy_manager = ProxyManager()
        self.photo_manager = PhotoManager()
        # Создаем директорию для хранения HTML файлов если её нет
        self.debug_dir = "debug_pages"
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

    def save_html_page(self, html: str, prefix: str) -> str:
        """
        Сохраняет HTML страницу в файл

        Args:
            html: HTML контент
            prefix: Префикс для имени файла

        Returns:
            str: Путь к сохраненному файлу
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.html"
        filepath = os.path.join(self.debug_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        logging.info(f"Saved HTML to {filepath}")
        return filepath

    def optimize_full_filters(
        self, full_user_filters: List[Dict]
    ) -> List[Tuple[str, List[int], float, float]]:
        """
        Оптимизирует фильтры пользователей, объединяя похожие запросы

        Args:
            full_user_filters (List[Dict]): Список фильтров пользователей

        Returns:
            List[Tuple[str, List[int], float, float]]: Список уникальных комбинаций (город, комнаты, макс_цена, мин_площадь)
        """
        # Если нет фильтров, возвращаем пустой список
        if not full_user_filters:
            logging.info("No filters to optimize")
            return []

        # Группируем фильтры по городам
        city_groups = defaultdict(list)
        for f in full_user_filters:
            if f["city"]:
                city_groups[f["city"]].append(f)

        # Если нет городов для поиска, возвращаем пустой список
        if not city_groups:
            logging.info("No cities to search in filters")
            return []

        optimized_requests = []

        for city, filters in city_groups.items():
            # Группируем фильтры по диапазонам цен
            price_ranges = []
            for f in filters:
                min_price = f["min_price"] or 0
                max_price = f["max_price"] or float("inf")
                price_ranges.append((min_price, max_price))

            # Находим оптимальные ценовые диапазоны
            unique_prices = sorted(
                set(
                    p
                    for range_pair in price_ranges
                    for p in range_pair
                    if p != float("inf")
                )
            )
            if not unique_prices:
                unique_prices = [1000000]  # Значение по умолчанию

            # Собираем все уникальные комнаты
            all_rooms = set()
            for f in filters:
                if f["rooms"]:
                    all_rooms.update(f["rooms"])
                else:
                    all_rooms.update([1, 2, 3, 4])

            # Находим минимальную площадь для города
            min_square = min(f.get("min_square", 0) or 0 for f in filters)

            # Группируем комнаты для минимизации запросов
            room_groups = []
            current_group = []
            for room in sorted(all_rooms):
                if (
                    not current_group or len(current_group) < 2
                ):  # Максимум 2 типа комнат в запросе
                    current_group.append(room)
                else:
                    room_groups.append(current_group)
                    current_group = [room]
            if current_group:
                room_groups.append(current_group)

            # Создаем оптимизированные запросы для каждой группы комнат
            for room_group in room_groups:
                max_price = max(unique_prices)
                optimized_requests.append((city, room_group, max_price, min_square))

        # Вычисляем статистику оптимизации только если есть запросы
        if optimized_requests:
            total_original_requests = sum(
                len(f.get("rooms", [1, 2, 3, 4]))
                for f in full_user_filters
                if f.get("city")
            )
            if total_original_requests > 0:  # Проверяем, чтобы избежать деления на ноль
                optimization_ratio = total_original_requests / len(optimized_requests)
            else:
                optimization_ratio = 1.0

            logging.info(
                f"Optimization summary:\n"
                f"Original users: {len(full_user_filters)}\n"
                f"Original potential requests: {total_original_requests}\n"
                f"Optimized requests: {len(optimized_requests)}\n"
                f"Cities: {len(city_groups)}\n"
                f"Optimization ratio: {optimization_ratio:.2f}x"
            )
        else:
            logging.info("No requests after optimization")

        return optimized_requests

    def get_apartments(
        self, city: str, rooms: List[int], max_price: float, min_square: float
    ) -> List[Dict]:
        """
        Gets apartments from the website based on filter criteria

        Args:
            city (str): City name in English
            rooms (List[int]): List of room counts to search for
            max_price (float): Maximum price
            min_square (float): Minimum square footage

        Returns:
            List[Dict]: List of apartments matching criteria
        """
        apartments = []
        max_retries = 3

        for room in rooms:
            url_city = CITY_MAPPING.get(city)
            if not url_city:
                logging.error("No city ot find flats")
                continue
            url = f"{self.base_url}/arenda/kvartiry/{url_city}/?das[live.rooms]={room}"
            if max_price:
                url += f"&das[price][to]={max_price}"
            if min_square:
                url += f"&das[live.square][from]={min_square}"

            logging.info(f"Scraping URL: {url}")

            for attempt in range(max_retries):
                try:
                    request_start = time.time()
                    proxies = self.proxy_manager.get_proxy()
                    proxy_time = time.time() - request_start

                    # Делаем запрос с прокси или без
                    if proxies:
                        proxy_str = proxies.get("http").replace("http://", "")
                        logging.info(
                            f"Attempt {attempt + 1}/{max_retries} using proxy: {proxy_str} "
                            f"(took {proxy_time:.2f}s to get)"
                        )
                        response = requests.get(
                            url,
                            headers={"User-Agent": "Mozilla/5.0"},
                            proxies=proxies,
                            timeout=10,
                            verify=False,  # Отключаем проверку SSL для прокси
                        )
                    else:
                        logging.warning("No proxy available, using direct connection")
                        response = requests.get(
                            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
                        )

                    if response.ok:
                        if proxies:
                            self.proxy_manager.mark_proxy_success(proxy_str)

                        # Сохраняем страницу со списком для дебага если нужно
                        # list_page_path = self.save_html_page(
                        #     response.text,
                        #     f"list_page_{city}_room{room}"
                        # )
                        # logging.info(f"List page saved to: {list_page_path}")

                        soup = BeautifulSoup(response.text, "html.parser")
                        listings = soup.find_all("div", class_="a-card__header")
                        logging.info(
                            f"Found {len(listings)} listings for {room} rooms in {city}"
                        )

                        for listing in listings:
                            link = listing.find("a")
                            if link:
                                apartment_url = self.base_url + link.get("href")
                                logging.debug(f"Processing apartment: {apartment_url}")

                                try:
                                    apartment_response = requests.get(
                                        apartment_url,
                                        headers={"User-Agent": "Mozilla/5.0"},
                                    )
                                    if not apartment_response.ok:
                                        logging.error(
                                            f"Failed to get apartment page {apartment_url}. Status code: {apartment_response.status_code}"
                                        )
                                        continue

                                    apartment_soup = BeautifulSoup(
                                        apartment_response.text, "html.parser"
                                    )

                                    # Получаем фотографии квартиры
                                    photo_urls = []
                                    photo_elements = apartment_soup.select(
                                        ".gallery__small-item img, .gallery__main img"
                                    )
                                    for photo_elem in photo_elements:
                                        src = photo_elem.get("src")
                                        if src:
                                            # Преобразуем URL в полный размер, если это миниатюра
                                            if "data-src" in photo_elem.attrs:
                                                src = photo_elem["data-src"]
                                            # Убедимся, что URL абсолютный
                                            if not src.startswith("http"):
                                                src = (
                                                    "https:" + src
                                                    if src.startswith("//")
                                                    else self.base_url + src
                                                )
                                            photo_urls.append(src)

                                    # Получаем цену
                                    price_elem = listing.find(
                                        "div", class_="a-card__price"
                                    )
                                    if not price_elem:
                                        logging.warning(
                                            f"No price found for {apartment_url}"
                                        )
                                        continue

                                    price = float(
                                        "".join(
                                            filter(str.isdigit, price_elem.text.strip())
                                        )
                                    )

                                    # Получаем площадь
                                    square = None
                                    square_elem = listing.find(
                                        "a", class_="a-card__title"
                                    )
                                    if square_elem:
                                        square_text = square_elem.text.strip()
                                        # Ищем число перед "м²"
                                        square_match = re.search(
                                            r"(\d+(?:\.\d+)?)\s*м²", square_text
                                        )
                                        if square_match:
                                            square = float(square_match.group(1))

                                    district = None
                                    street = None
                                    complex_name = None
                                    address_elem = listing.find(
                                        "div", class_="a-card__subtitle"
                                    )

                                    if address_elem:
                                        # Ищем район
                                        district_elem = apartment_soup.find(
                                            "div", text=lambda t: t and "р-н" in t
                                        )
                                        if district_elem:
                                            district = district_elem.text.strip()

                                        street = address_elem.text.strip()
                                        # Ищем ЖК
                                        complex_elem = apartment_soup.find(
                                            "div", text=lambda t: t and "ЖК" in t
                                        )
                                        if complex_elem:
                                            complex_name = complex_elem.text.strip()

                                        logging.debug(
                                            f"Parsed details: district={district}, street={street}, complex={complex_name}, square={square}"
                                        )

                                    # Получаем дату публикации объявления
                                    listing_date = None
                                    date_elem = apartment_soup.find(
                                        "div", class_="offer__date"
                                    )
                                    if date_elem:
                                        date_text = date_elem.text.strip()
                                        try:
                                            if "сегодня" in date_text.lower():
                                                listing_date = datetime.now().replace(
                                                    hour=0, minute=0, second=0
                                                )
                                            elif "вчера" in date_text.lower():
                                                listing_date = (
                                                    datetime.now() - timedelta(days=1)
                                                ).replace(hour=0, minute=0, second=0)
                                            else:
                                                # Попробуем извлечь дату из формата "день месяц"
                                                # Например: "5 июня" или "10 мая"
                                                date_pattern = (
                                                    r"(\d{1,2})\s+([а-яА-Я]+)"
                                                )
                                                date_match = re.search(
                                                    date_pattern, date_text
                                                )
                                                if date_match:
                                                    day = int(date_match.group(1))
                                                    month_name = date_match.group(
                                                        2
                                                    ).lower()
                                                    # Словарь для преобразования названий месяцев
                                                    month_dict = {
                                                        "января": 1,
                                                        "февраля": 2,
                                                        "марта": 3,
                                                        "апреля": 4,
                                                        "мая": 5,
                                                        "июня": 6,
                                                        "июля": 7,
                                                        "августа": 8,
                                                        "сентября": 9,
                                                        "октября": 10,
                                                        "ноября": 11,
                                                        "декабря": 12,
                                                    }
                                                    if month_name in month_dict:
                                                        month = month_dict[month_name]
                                                        current_year = (
                                                            datetime.now().year
                                                        )
                                                        listing_date = datetime(
                                                            current_year, month, day
                                                        )
                                                        # Если дата в будущем, то это год назад
                                                        if (
                                                            listing_date
                                                            > datetime.now()
                                                        ):
                                                            listing_date = datetime(
                                                                current_year - 1,
                                                                month,
                                                                day,
                                                            )
                                        except Exception as e:
                                            logging.warning(
                                                f"Error parsing listing date: {e}"
                                            )
                                            listing_date = None

                                    # Конвертируем английское название города в русское
                                    city_name = get_city_name(city)

                                    # Сохраняем информацию о квартире
                                    apartment_info = {
                                        "url": apartment_url,
                                        "price": price,
                                        "square": square,
                                        "rooms": room,
                                        "city": city_name,  # Используем русское название города
                                        "district": district,
                                        "street": street,
                                        "complex_name": complex_name,
                                        "listing_date": listing_date,
                                        "photo_urls": photo_urls[
                                            :3
                                        ],  # Сохраняем только первые 3 URL фотографий
                                    }
                                    apartments.append(apartment_info)
                                    logging.debug(
                                        f"Successfully added apartment: {apartment_url}"
                                    )

                                    # Сохраняем страницу объявления для дебага, если нужно
                                    # apartment_page_path = self.save_html_page(
                                    #     apartment_response.text,
                                    #     f"apartment_page_{apartment_url.split('/')[-1]}"
                                    # )
                                    # logging.info(f"Apartment page saved to: {apartment_page_path}")

                                except Exception as e:
                                    logging.error(
                                        f"Error parsing apartment details for {apartment_url}: {str(e)}"
                                    )
                                    continue

                        break
                    else:
                        if proxies:
                            proxy_str = proxies.get("http").replace("http://", "")
                            self.proxy_manager.mark_proxy_failure(proxy_str)
                        logging.error(
                            f"Failed to get page {url}. Status: {response.status_code}"
                        )
                        continue

                except Exception as e:
                    if proxies:
                        proxy_str = proxies.get("http").replace("http://", "")
                        self.proxy_manager.mark_proxy_failure(proxy_str)
                    logging.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                    continue

        logging.info(f"Total apartments found: {len(apartments)}")
        return apartments

    async def get_new_proxy(self) -> Optional[str]:
        """
        Получает новый прокси, который не использовался недавно

        Returns:
            Optional[str]: Прокси адрес или None
        """
        start_time = time.time()
        max_attempts = 5  # Максимальное количество попыток получить новый прокси

        for _ in range(max_attempts):
            try:
                proxy = self.proxy_manager.get_proxy()
                if proxy and self.proxy_manager.is_proxy_available(proxy):
                    elapsed = time.time() - start_time
                    logging.info(f"Got new proxy: {proxy} (took {elapsed:.2f}s)")
                    self.proxy_manager.mark_proxy_used(proxy)
                    return proxy
            except Exception as e:
                logging.warning(f"Error getting proxy: {e}")

        logging.error("Failed to get new available proxy")
        return None

    async def fetch_page(self, session, url: str) -> Optional[str]:
        """
        Загружает страницу с использованием прокси

        Args:
            session: aiohttp session
            url: URL для загрузки

        Returns:
            Optional[str]: HTML страницы или None
        """
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            proxy = await self.get_new_proxy()
            if not proxy:
                logging.error("No available proxies")
                return None

            try:
                logging.info(f"Attempt {attempt}/{max_attempts} using proxy: {proxy}")
                async with session.get(
                    url, proxy=proxy, timeout=10, headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    logging.warning(f"Got status code {response.status} from {url}")
            except Exception as e:
                logging.error(
                    f"Error on attempt {attempt}/{max_attempts} for {url}: {e}"
                )

            # Очищаем старые прокси после каждой попытки
            self.proxy_manager.clean_old_proxies()

        return None


def scraping_job(broker):
    """Periodic scraping job"""
    logging.info("Starting periodic scraping job")

    try:
        scraper = KrishaScraper()
        notification_manager = NotificationManager()

        # Получаем все активные фильтры пользователей
        user_filters = get_all_user_filters()
        logging.info(f"Found {len(user_filters)} active user filters")

        if not user_filters:
            logging.info("No active filters found, skipping scraping")
            return

        # Группируем фильтры по типу съёма
        full_apartment_filters = list()
        room_sharing_filters = list()

        for f in user_filters:
            rental_type = f.get("rental_type")
            f["filter_type"] = "user"
            if rental_type == RentalTypes.FULL_APARTMENT:
                full_apartment_filters.append(f)

            if rental_type == RentalTypes.ROOM_SHARING:
                room_sharing_filters.append(f)

        logging.info(f"Found {len(full_apartment_filters)} filters for full apartments")
        logging.info(
            f"Found {len(room_sharing_filters)} filters for room sharing apartments"
        )

        community_full_filters = get_all_community_full_filters()
        community_sharing_filters = get_all_community_sharing_filters()

        # Обрабатываем фильтры для жилья целиком
        if full_apartment_filters or community_full_filters:
            process_full_apartment_filters(
                broker,
                scraper,
                notification_manager,
                full_apartment_filters,
                community_full_filters,
            )

        # Обрабатываем фильтры для подселения
        if room_sharing_filters or community_sharing_filters:
            process_room_sharing_filters(
                broker,
                notification_manager,
                room_sharing_filters,
                community_sharing_filters,
            )

    except Exception as e:
        logging.error(f"Error in scraping job: {traceback.format_exc()}")


def process_full_apartment_filters(
    broker,
    scraper,
    notification_manager,
    full_apartment_filters,
    community_full_filters,
):
    """
    Обрабатывает фильтры для поиска жилья целиком

    Args:
        scraper: Экземпляр скрапера
        notification_manager: Экземпляр менеджера уведомлений
        full_apartment_filters: Список фильтров для жилья целиком
        community_full_filters: Список фильтров для жилья целиком для сообщества
    """
    full_apartment_filters = full_apartment_filters or []
    community_full_filters = community_full_filters or []

    # Оптимизируем фильтры
    optimized_filters = scraper.optimize_full_filters(
        full_apartment_filters + community_full_filters
    )

    # Словарь для хранения найденных квартир по городам
    found_apartments = {}

    # Выполняем оптимизированные запросы
    for city, rooms, max_price, min_square in optimized_filters:
        logging.info(
            f"Scraping for city={city}, rooms={rooms}, max_price={max_price}, min_square={min_square}"
        )
        apartments = scraper.get_apartments(
            city=city,
            rooms=rooms,
            max_price=max_price,
            min_square=min_square,
        )

        # Сохраняем новые квартиры в базу и скачиваем фотографии
        session = SessionLocal()
        try:
            for apartment in apartments:
                try:
                    # Извлекаем URL фотографий перед сохранением в базу
                    photo_urls = apartment.pop("photo_urls", [])

                    # Сохраняем квартиру в базу
                    apartment_id = save_apartment(**apartment)

                    # Если квартира успешно сохранена и есть ID, скачиваем фотографии
                    if apartment_id and photo_urls:
                        scraper.photo_manager.download_apartment_photos(
                            session, apartment_id, photo_urls
                        )

                        # Добавляем ID квартиры обратно в словарь для уведомлений
                        apartment["id"] = apartment_id
                except Exception as e:
                    logging.error(f"Error saving apartment: {e}")

            # Фиксируем изменения в базе данных
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error processing apartments: {e}")
        finally:
            session.close()

        # Группируем квартиры по городу для последующей фильтрации
        found_apartments[city] = apartments

    # обрабатываем фильтры для сообщества
    for community_filter in community_full_filters:
        try:
            city = community_filter["city"]
            if not city or city not in found_apartments:
                continue

            # Получаем непросмотренные квартиры для community
            unseen_apartments = get_community_unseen_full_apartments(
                community_filter["community_id"],
                city=city,
                min_price=community_filter["min_price"],
                max_price=community_filter["max_price"],
                min_square=community_filter["min_square"],
                rooms=community_filter["rooms"],
            )

            if unseen_apartments:
                logging.info(
                    f"Found {len(unseen_apartments)} new apartments for community {community_filter['community_id']}"
                )
                notification_manager.notify_community_new_apartments(
                    broker,
                    community_id=community_filter["community_id"],
                    apartments=unseen_apartments,
                    apartment_type=RentalTypes.FULL_APARTMENT,
                )
            else:
                logging.info(
                    f"No new apartments for community {community_filter['community_id']}"
                )
        except Exception as e:
            logging.error(f"Error processing community filter: {e}")

    # Обрабатываем фильтры каждого пользователя
    for user_filter in full_apartment_filters:
        try:
            city = user_filter["city"]
            if not city or city not in found_apartments:
                continue

            # Получаем непросмотренные квартиры для пользователя
            unseen_apartments = get_unseen_full_apartments(
                user_filter["user_id"],
                city=city,
                min_price=user_filter["min_price"],
                max_price=user_filter["max_price"],
                min_square=user_filter["min_square"],
                rooms=user_filter["rooms"],
            )

            if unseen_apartments:
                logging.info(
                    f"Found {len(unseen_apartments)} new apartments for user {user_filter['user_id']}"
                )
                notification_manager.notify_user_new_apartments(
                    user_id=user_filter["user_id"],
                    apartments=unseen_apartments,
                    apartment_type=RentalTypes.FULL_APARTMENT,
                )
            else:
                logging.info(f"No new apartments for user {user_filter['user_id']}")
        except Exception as e:
            logging.error(f"Error processing user filter: {e}")


def process_room_sharing_filters(
    broker, notification_manager, room_sharing_filters, community_sharing_filters
):
    """
    Обрабатывает фильтры для поиска подселения

    Args:
        scraper: Экземпляр скрапера
        notification_manager: Экземпляр менеджера уведомлений
        room_sharing_filters: Список фильтров для подселения
        community_sharing_filters: Список фильтров для подселения для комьюнити
    """
    logging.info(f"Processing {len(room_sharing_filters)} room sharing filters")
    logging.info(
        f"Processing {len(community_sharing_filters)} community sharing filters"
    )

    for community_filter in community_sharing_filters:
        try:
            community_id = community_filter["community_id"]
            city = community_filter.get("city")
            gender = community_filter.get("gender")
            roommate_preference = community_filter.get("roommate_preference")
            max_price = community_filter.get("max_price")

            logging.info(
                f"Processing room sharing filter for community {community_id}: "
                f"city={city}, gender={gender}, preference={roommate_preference}, "
                f"price max={max_price}"
            )

            unseen_apartments = get_unseen_community_sharing_apartments(
                community_id,
                city=city,
                max_price=community_filter["max_price"],
                min_price=community_filter["min_price"],
                gender=community_filter["gender"],
                roommate_preference=community_filter["roommate_preference"],
            )

            # Получаем непросмотренные квартиры для подселения из Telegram
            session = SessionLocal()
            try:
                if not unseen_apartments:
                    logging.info(
                        f"No new room sharing apartments found for community {community_id}"
                    )
                    continue

                logging.info(
                    f"Found {len(unseen_apartments)} new room sharing apartments for community {community_id}"
                )

                # Преобразуем объекты TelegramApartment в словари для отправки
                apartments_to_send = []

                for apt in unseen_apartments:
                    apartment_id = apt.get("id")

                    # Создаем словарь с данными квартиры
                    apartment_data = {
                        "id": apartment_id,
                        "message_id": apt.get("message_id"),
                        "channel": apt.get("channel_username"),
                        "price": apt.get("monthly_price"),
                        "location": apt.get("location"),
                        "contact": apt.get("contact"),
                        "text": apt.get("text"),
                        "city": apt.get("city"),
                        "preferred_gender": apt.get("preferred_gender"),
                    }

                    apartments_to_send.append(apartment_data)

                # Отправляем уведомления пользователю
                if apartments_to_send:
                    notification_manager.notify_community_new_apartments(
                        broker,
                        community_id=community_id,
                        apartments=apartments_to_send,
                        apartment_type=RentalTypes.ROOM_SHARING,
                    )

                    logging.info(
                        f"Sent {len(apartments_to_send)} room sharing apartments to community {community_id} and marked them as seen"
                    )
                else:
                    logging.info(
                        f"No room sharing apartments matching price filter for community {community_id}"
                    )

            except Exception as e:
                logging.error(
                    f"Error processing room sharing apartments from Telegram for community {community_id}: {e}"
                )
            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error processing room sharing community filter: {e}")

    # Обрабатываем фильтры каждого пользователя
    for user_filter in room_sharing_filters:
        try:
            user_id = user_filter["user_id"]
            city = user_filter.get("city")
            gender = user_filter.get("gender")
            roommate_preference = user_filter.get("roommate_preference")
            max_price = user_filter.get("max_price")

            logging.info(
                f"Processing room sharing filter for user {user_id}: "
                f"city={city}, gender={gender}, preference={roommate_preference}, "
                f"price max={max_price}"
            )

            unseen_apartments = get_unseen_sharing_apartments(
                user_filter["user_id"],
                city=city,
                max_price=user_filter["max_price"],
                gender=user_filter["gender"],
                roommate_preference=user_filter["roommate_preference"],
            )

            # Получаем непросмотренные квартиры для подселения из Telegram
            session = SessionLocal()
            try:
                if not unseen_apartments:
                    logging.info(
                        f"No new room sharing apartments found for user {user_id}"
                    )
                    continue

                logging.info(
                    f"Found {len(unseen_apartments)} new room sharing apartments for user {user_id}"
                )

                # Преобразуем объекты TelegramApartment в словари для отправки
                apartments_to_send = []

                for apt in unseen_apartments:
                    apartment_id = apt.get("id")

                    # Создаем словарь с данными квартиры
                    apartment_data = {
                        "id": apartment_id,
                        "message_id": apt.get("message_id"),
                        "channel": apt.get("channel_username"),
                        "price": apt.get("monthly_price"),
                        "location": apt.get("location"),
                        "contact": apt.get("contact"),
                        "text": apt.get("text"),
                        "city": apt.get("city"),
                        "preferred_gender": apt.get("preferred_gender"),
                    }

                    apartments_to_send.append(apartment_data)

                # Отправляем уведомления пользователю
                if apartments_to_send:
                    notification_manager.notify_user_new_apartments(
                        user_id=user_id,
                        apartments=apartments_to_send,
                        apartment_type=RentalTypes.ROOM_SHARING,
                    )

                    logging.info(
                        f"Sent {len(apartments_to_send)} room sharing apartments to user {user_id} and marked them as seen"
                    )
                else:
                    logging.info(
                        f"No room sharing apartments matching price filter for user {user_id}"
                    )

            except Exception as e:
                logging.error(
                    f"Error processing room sharing apartments from Telegram for user {user_id}: {e}"
                )
            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error processing room sharing user filter: {e}")

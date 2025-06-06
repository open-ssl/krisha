import asyncio
import io
import logging
import threading
from datetime import datetime, timedelta

from telethon import TelegramClient

from src.database import SessionLocal, TelegramApartment, TelegramApartmentPhoto
from src.env import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_CHANNELS,
    TELEGRAM_CLOUD_PASSWORD,
    TELEGRAM_PARSE_GROUP_DICT,
    TELEGRAM_PHONE_NUMBER,
)
from src.telegram.analyzer import analyze_message
from src.telegram.verification_service import request_verification_code


# Глобальный клиент Telegram для повторного использования
telegram_client = None
# Глобальная переменная для хранения кода подтверждения
verification_code = None
# Блокировка для потокобезопасного доступа к коду подтверждения
verification_code_lock = threading.Lock()
# Глобальная переменная для хранения цикла событий Telethon
telethon_loop = None
# Глобальная переменная для отслеживания текущего канала
current_channel_index = 0  # Индекс текущего канала для обработки

telegram_client_is_initialized = False


async def wait_for_verification_code():
    """
    Ожидание ввода кода подтверждения от администратора через notification_service.

    Returns:
        str: Код подтверждения
    """
    # Отправляем запрос на получение кода подтверждения
    code = await request_verification_code(
        "Требуется код подтверждения для Telegram. Пожалуйста, отправьте код в ответ на это сообщение."
    )

    if code:
        logging.info(f"Получен код подтверждения: {code}")
        return code
    else:
        logging.error("Не удалось получить код подтверждения")
        return None


async def code_callback():
    """
    Callback-функция для получения кода подтверждения.

    Returns:
        str: Код подтверждения
    """
    return await wait_for_verification_code()


async def password_callback():
    """
    Callback-функция для получения облачного пароля.

    Returns:
        str: Облачный пароль из переменной окружения
    """
    if TELEGRAM_CLOUD_PASSWORD:
        return TELEGRAM_CLOUD_PASSWORD

    # Если пароль не задан в переменной окружения, логируем ошибку
    logging.error("TELEGRAM_CLOUD_PASSWORD is not set")
    raise ValueError("TELEGRAM_CLOUD_PASSWORD is not set")


async def initialize_client():
    """
    Инициализация клиента Telegram, если он еще не инициализирован.
    Обрабатывает запросы кода подтверждения и облачного пароля.

    Returns:
        TelegramClient: Инициализированный клиент Telegram
    """
    global telegram_client, telethon_loop, telegram_client_is_initialized

    # Сохраняем текущий цикл событий для Telethon
    telethon_loop = asyncio.get_running_loop()

    if (
        not telegram_client_is_initialized
        or telegram_client is None
        or not telegram_client.is_connected()
    ):
        logging.info("Инициализация клиента Telegram")
        telegram_client_is_initialized = False
        # Создаем клиент с callback-функциями для кода подтверждения и пароля
        telegram_client = TelegramClient(
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session="telegram_scraper_session",
            loop=telethon_loop,
        )

        try:
            await telegram_client.disconnect()
            # Устанавливаем callback-функцию для кода подтверждения
            await telegram_client.start(
                phone=TELEGRAM_PHONE_NUMBER,
                code_callback=code_callback,
                password=password_callback,
            )
            telegram_client_is_initialized = True
            logging.info("Telegram клиент запущен успешно")

        except Exception as e:
            logging.error(
                f"Ошибка при инициализации клиента Telegram: {e}", exc_info=True
            )

            # Если произошла ошибка, сбрасываем клиент, чтобы можно было повторить попытку
            if telegram_client:
                try:
                    await telegram_client.disconnect()
                except Exception:
                    pass

            telegram_client = None
            telegram_client_is_initialized = False

    return telegram_client, telegram_client_is_initialized


async def get_last_checked_message_id(channel_id):
    """
    Получение ID последнего проверенного сообщения из базы данных для конкретного канала.

    Args:
        channel_id (int): ID канала/группы

    Returns:
        int: ID последнего проверенного сообщения или 0, если записей нет
    """
    session = SessionLocal()
    try:
        # Преобразуем channel_id в строку для хранения в базе данных
        channel_id_str = str(channel_id)
        last_apartment = (
            session.query(TelegramApartment)
            .filter_by(channel_username=channel_id_str)
            .order_by(TelegramApartment.message_id.desc())
            .first()
        )
        if last_apartment and last_apartment.message_id:
            logging.info(
                f"Последнее проверенное сообщение для канала {TELEGRAM_PARSE_GROUP_DICT.get(channel_id)}: {last_apartment.message_id}"
            )
            return last_apartment.message_id
        logging.info(
            f"Не найдено предыдущих сообщений для канала {TELEGRAM_PARSE_GROUP_DICT.get(channel_id)}, начинаем с 0"
        )
        return 0
    except Exception as e:
        logging.error(
            f"Ошибка при get_last_checked_message_id для канала {TELEGRAM_PARSE_GROUP_DICT.get(channel_id)}: {e}"
        )
        return 0
    finally:
        session.close()


async def check_message_id(channel_id, message_id):
    """
    Проверка ID проверенного сообщения из базы данных.

    Args:
        channel_id (int): ID канала/группы
        message_id (int): ID сообщения

    Returns:
        int: ID последнего проверенного сообщения или 0, если записей нет
    """
    session = SessionLocal()
    try:
        # Преобразуем channel_id в строку для хранения в базе данных
        channel_id_str = str(channel_id)
        check_apartment = (
            session.query(TelegramApartment)
            .filter_by(
                channel_username=channel_id_str,
                message_id=message_id,
            )
            .scalar()
        )

        return bool(check_apartment)
    except Exception as e:
        logging.error(f"Ошибка при check_message_id для канала {channel_id}: {e}")
        return True
    finally:
        session.close()


async def download_photo_to_memory(client, message):
    """
    Скачивание фотографии из сообщения в память.

    Args:
        client (TelegramClient): Клиент Telegram
        message: Сообщение из Telegram

    Returns:
        bytes: Данные фотографии в бинарном формате
    """
    # Создаем буфер в памяти для сохранения фотографии
    buffer = io.BytesIO()
    # Скачиваем фотографию в буфер
    await client.download_media(message.photo, buffer)
    # Возвращаем содержимое буфера
    return buffer.getvalue()


def is_duplicate_apartment(session, contact, location, monthly_price):
    """
    Проверяет, существует ли уже объявление с такими же контактом, локацией и ценой.

    Args:
        session: Сессия базы данных
        contact (str): Контактная информация
        location (str): Местоположение
        monthly_price (int): Ежемесячная цена

    Returns:
        bool: True, если объявление является дубликатом, иначе False
    """
    # Проверяем наличие всех необходимых данных для сравнения
    if not contact or not location or not monthly_price:
        return False

    # Ищем объявления с такими же параметрами за последние 30 дней
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    existing = (
        session.query(TelegramApartment)
        .filter(
            TelegramApartment.contact == contact,
            TelegramApartment.location == location,
            TelegramApartment.monthly_price == monthly_price,
            TelegramApartment.created_at >= thirty_days_ago,
        )
        .first()
    )

    return existing is not None


async def process_message(client, message, channel_id):
    """
    Обработка сообщения из канала.

    Args:
        client (TelegramClient): Клиент Telegram
        message: Сообщение из Telegram
        channel_id (int): ID канала/группы

    Returns:
        None
    """
    if not message.text:
        return

    # Преобразуем channel_id в строку для хранения в базе данных
    channel_id_str = str(channel_id)
    logging.info(f"Обработка сообщения {message.id} из канала {channel_id}")

    session = SessionLocal()
    # Анализ текста сообщения
    try:
        # Используем асинхронную функцию analyze_message
        if message.text and str(message.text).startswith(
            "Уважаемые подписчики нашего сообщества"
        ):
            logging.debug("Скипаем чепуху от администратора")
            return

        analysis_result = await analyze_message(message.text)

        # Проверяем, является ли сообщение объявлением об аренде
        if analysis_result.get("is_offer"):
            # Сохраняем объявление в базу данных

            # Проверяем, не сохранено ли уже это сообщение
            # Используем оба поля для проверки дубликатов, но без составного индекса
            existing = (
                session.query(TelegramApartment)
                .filter(
                    TelegramApartment.message_id == message.id,
                    TelegramApartment.channel_username == channel_id_str,
                )
                .first()
            )
            if existing:
                logging.info(
                    f"Сообщение {message.id} из канала {channel_id} уже обработано"
                )
                return

            # Проверяем, не является ли объявление дубликатом по контакту, локации и цене
            contact = analysis_result.get("contact", "")
            location = analysis_result.get("location", "")
            monthly_price = analysis_result.get("montly_price", "")

            if monthly_price:
                monthly_price = monthly_price.replace(" ", "")

            monthly_price = int(monthly_price) if monthly_price else 0
            city = analysis_result.get("city", "алматы") or "алматы"
            city = city.lower()

            if city in ("алмата", "алмаата", "алма-ата", "алма-аты"):
                city = "алматы"
            elif city in ("астаны", "нурсултан"):
                city = "астана"

            if is_duplicate_apartment(session, contact, location, monthly_price):
                logging.info(
                    f"Объявление с контактом '{contact}', локацией '{location}' и ценой '{monthly_price}' "
                    f"уже существует в базе данных. Пропускаем сообщение {message.id} из канала {channel_id}"
                )
                return

            apartment = TelegramApartment(
                message_id=message.id,
                channel_username=channel_id_str,
                is_offer=analysis_result.get("is_offer", False),
                is_roommate_offer=analysis_result.get("is_roommate_offer", False),
                is_rental_offer=analysis_result.get("is_rental_offer", False),
                monthly_price=monthly_price,
                preferred_gender=analysis_result.get("preferred_gender", ""),
                location=analysis_result.get("location", ""),
                contact=analysis_result.get("contact", ""),
                text=message.text,
                city=city,
                created_at=message.date,
            )

            try:
                session.add(apartment)
                session.commit()
                session.refresh(apartment)
                logging.debug(f"Создана запись квартиры с ID {apartment.id}")
            except Exception as e:
                session.rollback()
                logging.error(f"Ошибка при сохранении квартиры: {e}")
                return

            # Сохраняем фотографии
            photos_saved = 0

            try:
                # Проверяем наличие фотографии в текущем сообщении
                # if hasattr(message, "photo") and message.photo:
                #     try:
                #         photo_data = await download_photo_to_memory(client, message)
                #         photo = TelegramApartmentPhoto(
                #             apartment_id=apartment.id,
                #             photo_data=photo_data,
                #             created_at=datetime.utcnow()
                #         )
                #         session.add(photo)
                #         session.commit()
                #         photos_saved += 1
                #         logging.debug(f"Сохранена фотография из основного сообщения {message.id}")
                #     except Exception as photo_error:
                #         session.rollback()
                #         logging.error(f"Ошибка при сохранении фотографии из основного сообщения: {photo_error}")
                #         # Продолжаем выполнение, чтобы попытаться сохранить другие фотографии

                # Проверяем наличие сгруппированных сообщений (добавленных функцией get_unique_posts)
                if hasattr(message, "grouped_messages") and message.grouped_messages:
                    logging.debug(
                        f"Найдено {len(message.grouped_messages)} сгруппированных сообщений для {message.id}"
                    )

                    for media_message in message.grouped_messages:
                        # Пропускаем текущее сообщение, так как оно уже обработано выше
                        if media_message.id == message.id:
                            continue

                        # Проверяем наличие фотографии в сгруппированном сообщении
                        if hasattr(media_message, "photo") and media_message.photo:
                            try:
                                photo_data = await download_photo_to_memory(
                                    client, media_message
                                )
                                photo = TelegramApartmentPhoto(
                                    apartment_id=apartment.id,
                                    photo_data=photo_data,
                                    created_at=datetime.utcnow(),
                                )
                                session.add(photo)
                                session.commit()
                                photos_saved += 1
                                logging.debug(
                                    f"Сохранена фотография из сгруппированного сообщения {media_message.id}"
                                )
                            except Exception as photo_error:
                                session.rollback()
                                logging.error(
                                    f"Ошибка при сохранении фотографии из сгруппированного сообщения: {photo_error}"
                                )
                                # Продолжаем выполнение, чтобы попытаться сохранить другие фотографии
                        # Проверяем наличие фотографии в media.photo сгруппированного сообщения
                        elif (
                            hasattr(media_message, "media")
                            and hasattr(media_message.media, "photo")
                            and media_message.media.photo
                        ):
                            try:
                                # Создаем буфер в памяти для сохранения фотографии
                                buffer = io.BytesIO()
                                # Скачиваем фотографию в буфер
                                await client.download_media(
                                    media_message.media.photo, buffer
                                )
                                # Получаем данные фотографии
                                photo_data = buffer.getvalue()

                                photo = TelegramApartmentPhoto(
                                    apartment_id=apartment.id,
                                    photo_data=photo_data,
                                    created_at=datetime.utcnow(),
                                )
                                session.add(photo)
                                session.commit()
                                photos_saved += 1
                                logging.debug(
                                    f"Сохранена фотография из media.photo сгруппированного сообщения {media_message.id}"
                                )
                            except Exception as photo_error:
                                session.rollback()
                                logging.error(
                                    f"Ошибка при сохранении фотографии из media.photo сгруппированного сообщения: {photo_error}"
                                )
                                # Продолжаем выполнение, чтобы попытаться сохранить другие фотографии

                logging.info(
                    f"Сохранено объявление {apartment.id} из сообщения {message.id} канала {channel_id} с {photos_saved} фотографиями"
                )
            except Exception as photos_error:
                logging.error(f"Ошибка при сохранении фотографий: {photos_error}")
                # Не удаляем квартиру, даже если не удалось сохранить фотографии
        else:
            logging.info(
                f"Сообщение {message.id} из канала {channel_id} не является объявлением об аренде"
            )
    except Exception as e:
        session.rollback()
        logging.error(
            f"Ошибка при обработке сообщения {message.id} из канала {channel_id}: {e}"
        )
    finally:
        session.close()


async def get_unique_posts(client, channel_id, limit):
    """
    Получает уникальные посты из канала, объединяя сообщения с одинаковым grouped_id.

    Args:
        client (TelegramClient): Клиент Telegram
        channel_id (int): ID канала/группы
        limit (int): Максимальное количество постов для получения

    Returns:
        list: Список уникальных постов
    """
    messages = await client.get_messages(channel_id, limit=limit)

    # Словарь для группировки сообщений по grouped_id
    grouped_messages = {}
    # Список для сообщений без grouped_id
    single_messages = []

    # Группируем сообщения
    for message in messages:
        if hasattr(message, "grouped_id") and message.grouped_id:
            if message.grouped_id not in grouped_messages:
                grouped_messages[message.grouped_id] = []
            grouped_messages[message.grouped_id].append(message)
        else:
            single_messages.append(message)

    # Формируем список уникальных постов
    unique_posts = []

    # Добавляем сгруппированные сообщения (берем только первое сообщение с текстом из группы)
    for group_id, group_messages in grouped_messages.items():
        # Ищем сообщение с текстом в группе
        text_message = next((msg for msg in group_messages if msg.text), None)
        if text_message:
            # Добавляем информацию о других медиа в группе
            text_message.grouped_messages = group_messages
            unique_posts.append(text_message)
        else:
            # Если нет сообщения с текстом, берем первое сообщение из группы
            group_messages[0].grouped_messages = group_messages
            unique_posts.append(group_messages[0])

    # Добавляем одиночные сообщения
    unique_posts.extend(single_messages)

    # Сортируем по дате (от новых к старым)
    unique_posts.sort(key=lambda msg: msg.date, reverse=True)

    return unique_posts


async def process_channel(client, channel_id):
    """
    Обработка одного канала/группы.

    Args:
        client (TelegramClient): Клиент Telegram
        channel_id (int): ID канала/группы

    Returns:
        None
    """
    try:
        # Получаем ID последнего проверенного сообщения из базы данных для этого канала
        last_checked_message_id = await get_last_checked_message_id(channel_id)

        # Получаем уникальные посты из канала
        unique_posts = await get_unique_posts(
            client=client, channel_id=channel_id, limit=50
        )

        # Обрабатываем новые посты
        for post in unique_posts:
            if post.id > last_checked_message_id or not await check_message_id(
                channel_id=channel_id, message_id=post.id
            ):
                await process_message(client, post, channel_id)
    except Exception as e:
        logging.error(f"Ошибка при обработке канала {channel_id}: {e}")


async def telegram_scraping_job():
    """
    Основная функция для скрапинга Telegram, которая будет запускаться по расписанию.
    Обрабатывает один канал из списка TELEGRAM_CHANNELS при каждом запуске,
    циклически переходя к следующему каналу при каждом вызове.

    Returns:
        None
    """
    global telethon_loop
    global current_channel_index

    # Проверяем, что мы используем правильный цикл событий
    current_loop = asyncio.get_running_loop()
    if telethon_loop is not None and current_loop != telethon_loop:
        logging.error("Попытка запустить telegram_scraping_job в другом цикле событий")
        return

    logging.info("Запуск задачи скрапинга Telegram")

    try:
        # Проверяем, есть ли каналы для мониторинга
        if not TELEGRAM_CHANNELS:
            logging.warning(
                "Список каналов для мониторинга пуст. Задача скрапинга Telegram пропущена."
            )
            return

        logging.info(
            f"Найдено {len(TELEGRAM_CHANNELS)} каналов для мониторинга: {list(TELEGRAM_PARSE_GROUP_DICT.keys())}"
        )

        # Инициализируем клиент Telegram
        logging.info("Начинаем инициализацию клиента Telegram")
        client, telegram_client_is_initialized = await initialize_client()

        if client is None or not telegram_client_is_initialized:
            logging.error("Telegram клиент ещё не инициализирован для запроса канала!")
            return

        logging.info("Клиент Telegram успешно инициализирован")
        # Обрабатываем только один канал за раз
        if current_channel_index >= len(TELEGRAM_CHANNELS):
            current_channel_index = (
                0  # Сбрасываем индекс, если он вышел за пределы списка
            )

        channel_id = TELEGRAM_CHANNELS[current_channel_index]

        # Преобразуем channel_id в int, если он передан как строка
        if isinstance(channel_id, str):
            try:
                channel_id = int(channel_id)
            except ValueError:
                logging.error(f"Некорректный ID канала: {channel_id}")
                # Переходим к следующему каналу при следующем запуске
                current_channel_index = (current_channel_index + 1) % len(
                    TELEGRAM_CHANNELS
                )
                return

        logging.info(
            f"Обрабатываем канал {current_channel_index + 1} "
            f"из {len(TELEGRAM_CHANNELS)}: {TELEGRAM_PARSE_GROUP_DICT.get(channel_id)}"
        )
        await process_channel(client, channel_id)
        logging.info(
            f"Завершена обработка канала {TELEGRAM_PARSE_GROUP_DICT.get(channel_id)}"
        )

        # Увеличиваем индекс для следующего запуска
        current_channel_index = (current_channel_index + 1) % len(TELEGRAM_CHANNELS)
        logging.info(
            f"Следующий запуск будет обрабатывать канал с индексом {current_channel_index}"
        )

        logging.info("Задача скрапинга Telegram завершена успешно")

    except Exception as e:
        logging.error(
            f"Ошибка при выполнении задачи скрапинга Telegram: {e}", exc_info=True
        )


if __name__ == "__main__":
    asyncio.run(telegram_scraping_job())

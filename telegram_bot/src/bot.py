import asyncio
import logging
from typing import Optional

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from buttons import Buttons
from filters import UserFilters
from message_manager import MessageManager
from src.env import AUTHOR_URL, MAX_MESSAGE_LENGTH, SCRAPER_SERVICE_URL, TELEGRAM_ADMIN_ID
from utils.city_mapping import CITY_MAPPING, get_city_name
from utils.city_types import CityTypes
from utils.gender_types import GenderTypes
from utils.photo_manager import PhotoManager
from utils.rental_types import RentalTypes


user_filters = UserFilters()


def get_available_cities() -> str:
    """Получить список доступных городов"""
    cities = CITY_MAPPING.keys()
    return "\n".join(f"• `{city.capitalize()}`" for city in cities)


class FilterStates(StatesGroup):
    """States for filter setup process"""

    setting_rental_type = State()
    setting_city = State()
    setting_rooms = State()
    setting_min_price = State()
    setting_max_price = State()
    setting_min_square = State()
    confirming_filters = State()


class RoommateFilterStates(StatesGroup):
    """States for roommate filter setup process"""

    setting_gender = State()  # Установка пола пользователя
    setting_roommate_preference = State()  # Установка предпочтений по соседям
    setting_city = State()  # Установка города
    setting_max_price = State()  # Установка максимальной цены
    confirming_filters = State()  # Подтверждение фильтра


def get_filter_keyboard() -> types.ReplyKeyboardMarkup:
    """Get keyboard with cancel and skip buttons"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Buttons.SKIP_FILTER)],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    """Get keyboard with cancel button"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    """Get main menu keyboard"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Buttons.SHOW_FILTER)],
            [
                types.KeyboardButton(text=Buttons.SET_FILTER),
                types.KeyboardButton(text=Buttons.STOP_SEARCH),
            ],
            [types.KeyboardButton(text=Buttons.AUTHOR)],
        ],
        resize_keyboard=True,
    )


def get_confirm_keyboard() -> types.ReplyKeyboardMarkup:
    """Get confirmation keyboard"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Buttons.CREATE_FILTER)],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


def get_author_keyboard() -> types.InlineKeyboardMarkup:
    """Get inline keyboard with author profile link"""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=Buttons.AUTHOR_PROFILE, url=AUTHOR_URL)]
        ]
    )
    return keyboard


def get_rental_type_keyboard() -> types.ReplyKeyboardMarkup:
    """Get keyboard with rental type options"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=RentalTypes.DISPLAY_NAMES[RentalTypes.FULL_APARTMENT]
                )
            ],
            [
                types.KeyboardButton(
                    text=RentalTypes.DISPLAY_NAMES[RentalTypes.ROOM_SHARING]
                )
            ],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


class KrishaBot:
    """Telegram bot for Krisha.kz monitoring"""

    def __init__(self, token: str):
        """
        Initialize bot

        Args:
            token (str): Telegram bot token
        """
        self.bot = Bot(token=token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.message_manager = MessageManager(admin_id=TELEGRAM_ADMIN_ID)
        self.photo_manager = PhotoManager()
        self.setup_handlers()

    def setup_handlers(self) -> None:
        """Setup bot command handlers"""
        # Команды
        self.dp.message.register(self.start_handler, Command(commands=["start"]))

        # Обработчики кнопок главного меню
        self.dp.message.register(
            self.show_filter_handler, lambda msg: msg.text == Buttons.SHOW_FILTER
        )
        self.dp.message.register(
            self.author_handler, lambda msg: msg.text == Buttons.AUTHOR
        )
        self.dp.message.register(
            self.start_filter_setup, lambda msg: msg.text == Buttons.SET_FILTER
        )
        self.dp.message.register(
            self.stop_search_handler, lambda msg: msg.text == Buttons.STOP_SEARCH
        )

        # Обработчики состояний фильтров для жилья целиком
        self.dp.message.register(
            self.handle_rental_type, StateFilter(FilterStates.setting_rental_type)
        )
        self.dp.message.register(
            self.handle_city, StateFilter(FilterStates.setting_city)
        )
        self.dp.message.register(
            self.handle_rooms, StateFilter(FilterStates.setting_rooms)
        )
        self.dp.message.register(
            self.handle_min_price, StateFilter(FilterStates.setting_min_price)
        )
        self.dp.message.register(
            self.handle_max_price, StateFilter(FilterStates.setting_max_price)
        )
        self.dp.message.register(
            self.handle_min_square, StateFilter(FilterStates.setting_min_square)
        )
        self.dp.message.register(
            self.process_confirmation, StateFilter(FilterStates.confirming_filters)
        )

        # Обработчики состояний фильтров для подселения
        self.dp.message.register(
            self.handle_gender, StateFilter(RoommateFilterStates.setting_gender)
        )
        self.dp.message.register(
            self.handle_roommate_preference,
            StateFilter(RoommateFilterStates.setting_roommate_preference),
        )
        self.dp.message.register(
            self.handle_roommate_city, StateFilter(RoommateFilterStates.setting_city)
        )
        self.dp.message.register(
            self.handle_roommate_max_price,
            StateFilter(RoommateFilterStates.setting_max_price),
        )
        self.dp.message.register(
            self.process_roommate_confirmation,
            StateFilter(RoommateFilterStates.confirming_filters),
        )

        # Добавляем обработчик изменения статуса бота
        self.dp.my_chat_member.register(self.handle_bot_blocked)

    async def start_handler(self, message: types.Message) -> None:
        """Handle /start command"""
        user = message.from_user

        # Проверяем наличие URL
        scraper_url = SCRAPER_SERVICE_URL
        if not scraper_url:
            logging.error("SCRAPER_SERVICE_URL is not set")
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "⚠️ Ошибка конфигурации бота. Пожалуйста, обратитесь к администратору.",
                get_main_keyboard(),
            )
            return

        # Регистрируем пользователя в базе
        try:
            response = requests.post(
                f"{scraper_url}/users",
                json={
                    "user_id": user.id,
                    "first_name": user.first_name if user.first_name else None,
                    "last_name": user.last_name if user.last_name else None,
                    "is_active": True,
                },
            )
            if not response.ok:
                logging.error(
                    f"Failed to register user: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logging.error(f"Error registering user: {e}")

        user_filter = user_filters.get_filter(user.id)
        filter_status = self.format_filter_status(user_filter)

        # Формируем приветственное сообщение с именем пользователя, если оно есть
        greeting = f"Привет{' ' + user.first_name if user.first_name else ''}! "
        greeting += "Я помогу найти квартиру на Krisha.kz\n\n"
        greeting += filter_status

        await self.message_manager.send_message(
            self.bot, message.chat.id, greeting, get_main_keyboard()
        )

    async def start_filter_setup(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Start filter setup process"""
        await state.set_state(FilterStates.setting_rental_type)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Выберите тип съёма:\n\n"
                "1. Жильё целиком - Поиск квартир для аренды полностью\n"
                "2. Подселение - Поиск комнат или квартир для совместного проживания"
            ),
            get_rental_type_keyboard(),
        )

    async def handle_rental_type(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Handle rental type selection"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        # Определяем выбранный тип съёма
        if message.text == RentalTypes.DISPLAY_NAMES[RentalTypes.FULL_APARTMENT]:
            await state.update_data(rental_type=RentalTypes.FULL_APARTMENT)
            await state.set_state(FilterStates.setting_city)
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                (
                    "Введите название города для поиска.\n"
                    "Доступные города (нажмите, чтобы скопировать):\n"
                    f"{get_available_cities()}\n\n"
                    f"Нажмите на пример, чтобы скопировать его."
                ),
                get_cancel_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif message.text == RentalTypes.DISPLAY_NAMES[RentalTypes.ROOM_SHARING]:
            await state.update_data(rental_type=RentalTypes.ROOM_SHARING)
            # Начинаем процесс создания фильтра для подселения
            await state.set_state(RoommateFilterStates.setting_gender)
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Укажите ваш пол:",
                get_gender_keyboard(),
            )
        else:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Пожалуйста, выберите один из предложенных вариантов.",
                get_rental_type_keyboard(),
            )
            return

    async def handle_city(self, message: types.Message, state: FSMContext) -> None:
        """Handle city input"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(city=None)
        else:
            # Приводим введенный город к нижнему регистру
            entered_city = message.text.strip().lower()

            # Проверяем, есть ли город в маппинге
            if entered_city not in CITY_MAPPING:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    (
                        "❌ Город не найден. Пожалуйста, выберите город из списка:\n\n"
                        f"{get_available_cities()}\n\n"
                        f"Нажмите на пример, чтобы скопировать его.\n"
                        f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
                    ),
                    get_cancel_keyboard(),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Сохраняем русское название города
            await state.update_data(
                city=entered_city,  # Сохраняем русское название города
                city_display=entered_city.capitalize(),  # Для отображения пользователю
            )

        await state.set_state(FilterStates.setting_rooms)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Введите количество комнат через запятую.\n"
                "Например:\n"
                "`1` - 1 комнатные\n"
                "`2,3` - только 2 и 3-комнатные\n"
                "`1,2,3,4` - от 1 до 4 комнат\n\n"
                "Нажмите на пример, чтобы скопировать его.\n"
                f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
            ),
            get_filter_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_rooms(self, message: types.Message, state: FSMContext) -> None:
        """Handle rooms input"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(rooms=None)
        else:
            try:
                rooms = [int(r.strip()) for r in message.text.split(",")]
                await state.update_data(rooms=rooms)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "Неверный формат. Введите числа через запятую.",
                )
                return

        await state.set_state(FilterStates.setting_min_price)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Введите минимальную цену в тенге.\n"
                "Например:\n"
                "`150000` - от 150 000 тг\n"
                "`280000` - от 280 000 тг\n\n"
                "Нажмите на пример, чтобы скопировать его.\n"
                f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
            ),
            get_filter_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_min_price(self, message: types.Message, state: FSMContext) -> None:
        """Handle minimum price input"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(min_price=None)
        else:
            try:
                min_price = float(message.text.replace(" ", ""))
                await state.update_data(min_price=min_price)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot, message.chat.id, "Неверный формат. Введите число."
                )
                return

        await state.set_state(FilterStates.setting_max_price)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Введите максимальную цену в тенге.\n"
                "Например:\n"
                "`300000` - до 300 000 тг\n"
                "`420000` - до 420 000 тг\n\n"
                "Нажмите на пример, чтобы скопировать его.\n"
                f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
            ),
            get_filter_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_max_price(self, message: types.Message, state: FSMContext) -> None:
        """Handle maximum price input"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(max_price=None)
        else:
            try:
                max_price = float(message.text.replace(" ", ""))
                await state.update_data(max_price=max_price)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot, message.chat.id, "Неверный формат. Введите число."
                )
                return

        await state.set_state(FilterStates.setting_min_square)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Введите минимальную площадь квартиры в м².\n"
                "Например:\n"
                "`30` - от 30 м²\n"
                "`55` - от 55 м²\n\n"
                "Нажмите на пример, чтобы скопировать его.\n"
                f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
            ),
            get_filter_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_min_square(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Handle minimum square input"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(min_square=None)
        else:
            try:
                min_square = float(message.text.replace(" ", ""))
                await state.update_data(min_square=min_square)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot, message.chat.id, "Неверный формат. Введите число."
                )
                return

        # Показываем текущие настройки фильтра
        data = await state.get_data()
        rental_type_display = RentalTypes.get_display_name(data.get("rental_type", ""))

        # Подготовка данных для превью
        city_display = data.get("city_display") or "Любой"

        rooms_data = data.get("rooms", [])
        rooms_display = "Любое количество"
        if rooms_data:
            rooms_display = ", ".join(map(str, rooms_data))

        min_price = data.get("min_price")
        max_price = data.get("max_price")

        price_display = "Любая"
        if min_price and max_price:
            price_display = f"от {int(min_price)} до {int(max_price)} тг"
        elif min_price:
            price_display = f"от {int(min_price)} тг"
        elif max_price:
            price_display = f"до {int(max_price)} тг"

        min_square_data = data.get("min_square")
        square_display = "Любая"
        if min_square_data:
            square_display = f"от {min_square_data} м²"

        filter_preview = (
            "📋 Проверьте настройки фильтра:\n\n"
            f"🏠 Тип съёма: {rental_type_display}\n"
            f"🏙 Город: {city_display}\n"
            f"🏠 Комнат: {rooms_display}\n"
            f"💰 Цена: {price_display}\n"
            f"📏 Площадь: {square_display}\n\n"
            "Создать фильтр с этими настройками?"
        )

        await state.set_state(FilterStates.confirming_filters)
        await self.message_manager.send_message(
            self.bot, message.chat.id, filter_preview, get_confirm_keyboard()
        )

    async def process_confirmation(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Process filter confirmation"""
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.CREATE_FILTER:
            data = await state.get_data()
            user_id = message.from_user.id

            try:
                # Сначала удаляем старый фильтр
                try:
                    requests.delete(f"{SCRAPER_SERVICE_URL}/users/{user_id}/filters")
                except Exception as e:
                    logging.warning(f"Failed to delete old filter: {e}")

                # Сохраняем новый фильтр в базу данных
                response = requests.post(
                    f"{SCRAPER_SERVICE_URL}/users/filters",
                    json={
                        "user_id": user_id,
                        "city": data.get("city"),
                        "rooms": data.get("rooms"),
                        "min_price": data.get("min_price"),
                        "max_price": data.get("max_price"),
                        "min_square": data.get("min_square"),
                        "rental_type": data.get("rental_type"),
                    },
                )

                if not response.ok:
                    logging.error(
                        f"Failed to save filter: {response.status_code} - {response.text}"
                    )
                    await self.message_manager.send_message(
                        bot=self.bot,
                        chat_id=message.chat.id,
                        text="⚠️ Не удалось сохранить фильтры. Пожалуйста, попробуйте позже.",
                        reply_markup=get_main_keyboard(),
                    )
                    return

                # Обновляем локальный фильтр
                user_filters.set_filter(
                    user_id,
                    city=data.get("city"),
                    rooms=data.get("rooms"),
                    min_price=data.get("min_price"),
                    max_price=data.get("max_price"),
                    min_square=data.get("min_square"),
                    rental_type=data.get("rental_type"),
                )

                if data.get("rental_type") == RentalTypes.ROOM_SHARING:
                    await self.message_manager.send_message(
                        bot=self.bot,
                        chat_id=message.chat.id,
                        text="✅ Фильтр успешно создан!\n⚙️ Теперь Вы будете получать варианты для подселения.",
                        reply_markup=get_main_keyboard(),
                    )
                    await state.clear()
                    return

                # Сразу после установки фильтра делаем поиск (только для типа "Жильё целиком")
                try:
                    # Для поиска на Krisha используем английское название города
                    search_city = (
                        CITY_MAPPING.get(data.get("city", ""))
                        if data.get("city")
                        else None
                    )

                    response = requests.post(
                        f"{SCRAPER_SERVICE_URL}/apartments/filter",
                        json={
                            "city": search_city,  # Используем английское название для поиска
                            "min_price": data.get("min_price"),
                            "max_price": data.get("max_price"),
                            "rooms": data.get("rooms"),
                            "min_square": data.get("min_square"),
                        },
                    )

                    if response.ok:
                        apartments = response.json()
                        if apartments:
                            # Отправляем результаты поиска
                            await self.send_search_results(message, apartments)
                        else:
                            await self.message_manager.send_message(
                                bot=self.bot,
                                chat_id=message.chat.id,
                                text="✅ Фильтр успешно создан!\nТеперь Вы будете получать уведомления о новых квартирах для созданного Вами фильтра!\n\nУдачного поиска!\nЕсли вам понравится данный бот, пожалуйста, рекомендуйте его знакомым 😉.",
                                reply_markup=get_main_keyboard(),
                            )
                    else:
                        await self.message_manager.send_message(
                            bot=self.bot,
                            chat_id=message.chat.id,
                            text="✅ Фильтр успешно создан!\n⚠️ Не удалось выполнить поиск сейчас, но вы будете получать уведомления о новых квартирах.",
                            reply_markup=get_main_keyboard(),
                        )
                except Exception as e:
                    logging.error(f"Error in initial search: {e}")
                    await self.message_manager.send_message(
                        bot=self.bot,
                        chat_id=message.chat.id,
                        text="✅ Фильтр успешно создан!\n⚠️ Произошла ошибка при поиске, но вы будете получать уведомления о новых квартирах.",
                        reply_markup=get_main_keyboard(),
                    )

            except Exception as e:
                logging.error(f"Error saving filter: {e}")
                await self.message_manager.send_message(
                    bot=self.bot,
                    chat_id=message.chat.id,
                    text="⚠️ Произошла ошибка при сохранении фильтров.",
                    reply_markup=get_main_keyboard(),
                )

            await state.clear()

    async def cancel_filter_setup(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Cancel filter setup"""
        await state.clear()
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "❌ Настройка фильтров отменена",
            get_main_keyboard(),
        )

    async def show_filter_handler(self, message: types.Message) -> None:
        """
        Обработчик команды показа фильтра.
        Получает фильтр пользователя из локального хранилища и из API-сервиса

        Args:
            message (types.Message): Сообщение пользователя
        """
        user_id = message.from_user.id

        # Получаем фильтр из локального хранилища
        local_filter = user_filters.get_filter(user_id)

        # Логируем локальный фильтр для отладки
        logging.info(f"Local filter before API check: {local_filter}")

        # Проверяем наличие URL сервиса
        scraper_url = SCRAPER_SERVICE_URL
        if not scraper_url:
            logging.error("SCRAPER_SERVICE_URL is not set")
            # Используем только локальный фильтр
            filter_status = self.format_filter_status(local_filter)
            await self.message_manager.send_message(
                bot=self.bot,
                chat_id=message.chat.id,
                text=filter_status,
                reply_markup=get_main_keyboard(),
            )
            return

        try:
            # Запрашиваем фильтр из API-сервиса
            response = requests.get(f"{scraper_url}/filters/user/{user_id}")

            if response.ok:
                # Получаем данные из API
                api_filter = response.json()
                logging.info(f"API filter: {api_filter}")

                # Проверяем, что данные не пусты и имеют правильную структуру
                if api_filter and isinstance(api_filter, dict):
                    # Если локальный фильтр существует, сохраняем значения gender и roommate_preference
                    gender = local_filter.get("gender") if local_filter else None
                    roommate_preference = (
                        local_filter.get("roommate_preference")
                        if local_filter
                        else None
                    )

                    # Если в API есть эти поля, используем их
                    if "gender" in api_filter:
                        gender = api_filter.get("gender")
                    if "roommate_preference" in api_filter:
                        roommate_preference = api_filter.get("roommate_preference")

                    # Обновляем локальный фильтр данными из API
                    user_filters.set_filter(
                        user_id=user_id,
                        city=api_filter.get("city"),
                        rooms=api_filter.get("rooms"),
                        min_price=api_filter.get("min_price"),
                        max_price=api_filter.get("max_price"),
                        min_square=api_filter.get("min_square"),
                        rental_type=api_filter.get("rental_type"),
                        gender=gender,
                        roommate_preference=roommate_preference,
                    )
                    local_filter = user_filters.get_filter(user_id)
                    logging.info(f"Updated local filter: {local_filter}")
            else:
                logging.error(
                    f"Failed to get filter from API: {response.status_code} - {response.text} (endpoint: filters/user/{user_id})"
                )
        except Exception as e:
            logging.error(f"Error getting filter from API: {e}")

        # Формируем сообщение о статусе фильтра
        filter_status = self.format_filter_status(local_filter)

        await self.message_manager.send_message(
            bot=self.bot,
            chat_id=message.chat.id,
            text=filter_status,
            reply_markup=get_main_keyboard(),
        )

    async def author_handler(self, message: types.Message) -> None:
        """Handle author command"""
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "👨‍💻 Автор бота:",
            reply_markup=get_author_keyboard(),
        )

    async def handle_bot_blocked(self, chat_member: types.ChatMemberUpdated) -> None:
        """
        Handle user blocking/unblocking the bot

        Args:
            chat_member (types.ChatMemberUpdated): Update event with status change
        """
        user = chat_member.from_user
        # Проверяем новый статус бота
        is_active = chat_member.new_chat_member.status not in ["kicked", "left"]

        try:
            response = requests.post(
                f"{SCRAPER_SERVICE_URL}/users",
                json={
                    "user_id": user.id,
                    "first_name": user.first_name if user.first_name else None,
                    "last_name": user.last_name if user.last_name else None,
                    "is_active": is_active,
                },
            )
            if not response.ok:
                logging.error(
                    f"Failed to update user block status: {response.status_code} - {response.text}"
                )

            # Если пользователь разблокировал бота, отправляем приветственное сообщение
            if is_active:
                await self.message_manager.send_message(
                    self.bot,
                    user.id,
                    f"С возвращением{' ' + user.first_name if user.first_name else ''}! "
                    "Я продолжу отправлять вам уведомления о новых квартирах.",
                    get_main_keyboard(),
                )
            else:
                user_filters.set_filter(user.id, None, None, None, None)

        except Exception as e:
            logging.error(f"Error updating user block status: {e}")

    async def stop_search_handler(self, message: types.Message) -> None:
        """Handle stop search command"""
        user_id = message.from_user.id

        # Проверяем наличие URL
        scraper_url = SCRAPER_SERVICE_URL
        if not scraper_url:
            logging.error("SCRAPER_SERVICE_URL is not set")
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "⚠️ Ошибка конфигурации бота. Пожалуйста, обратитесь к администратору.",
                get_main_keyboard(),
            )
            return

        try:
            # Удаляем фильтр из локального хранилища
            user_filters.set_filter(user_id, None, None, None, None)

            # Удаляем фильтр из базы данных
            response = requests.delete(f"{scraper_url}/users/{user_id}/filters")

            if not response.ok:
                logging.error(
                    f"Failed to delete filter: {response.status_code} - {response.text}"
                )
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "⚠️ Не удалось полностью остановить поиск. Пожалуйста, попробуйте позже.",
                    get_main_keyboard(),
                )
                return

            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "✅ Поиск остановлен.\nВы больше не будете получать уведомления о новых квартирах.",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logging.error(f"Error stopping search: {e}")
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "⚠️ Произошла ошибка при остановке поиска.",
                get_main_keyboard(),
            )

    async def send_search_results(
        self, message: types.Message, apartments: list
    ) -> None:
        """
        Send search results to user

        Args:
            message: Message object
            apartments: List of apartments
        """
        # Разбиваем квартиры на группы, чтобы сообщение не превышало лимит
        current_message = "🏠 Найденные квартиры:\n\n"
        messages = []

        for apt in apartments:
            # Получаем русское название города, так как в результатах поиска city будет на английском
            city_name = get_city_name(apt["city"])

            apartment_text = (
                f"{apt['rooms']}-комн., {apt['square']} м², {city_name}\n"
                f"💰 {int(apt['price'])} тг\n"
                f"[Ссылка на объявление]({apt['url']})\n\n"
            )

            # Если текущее сообщение + новая квартира превысят лимит
            if len(current_message) + len(apartment_text) > MAX_MESSAGE_LENGTH:
                messages.append(current_message)
                current_message = (
                    "🏠 Найденные квартиры (продолжение):\n\n" + apartment_text
                )
            else:
                current_message += apartment_text

        # Добавляем последнее сообщение, если оно не пустое
        if current_message and current_message != "🏠 Найденные квартиры:\n\n":
            messages.append(current_message)

        # Отправляем все сообщения
        for i, msg in enumerate(messages, 1):
            if len(messages) > 1:
                msg += f"\nСтраница {i} из {len(messages)}"

            # Если всего одна квартира и один блок сообщений, добавляем фотографии
            photos = None
            if len(apartments) == 1 and len(messages) == 1:
                apartment_id = apartments[0].get("id")
                if apartment_id:
                    photos = self.photo_manager.get_apartment_photos(apartment_id)
                    logging.info(
                        f"Found {len(photos)} photos for apartment {apartment_id}"
                    )

            await self.message_manager.send_message(
                bot=self.bot,
                chat_id=message.chat.id,
                text=msg,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN,
                photos=photos,
            )
            # Небольшая пауза между сообщениями
            if i < len(messages):
                await asyncio.sleep(0.5)

        notification_text = (
            "✨ Это все квартиры, которые сейчас есть в нашей базе.\n\n"
            "🔔 Как только появятся новые объявления, соответствующие вашим критериям поиска, "
            "вы автоматически получите уведомление прямо в этом чате.\n\n"
            "💫 Сервис полностью бесплатный!"
        )

        await self.message_manager.send_message(
            bot=self.bot,
            chat_id=message.chat.id,
            text=notification_text,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def start(self) -> None:
        """Start the bot with polling"""
        await self.dp.start_polling(
            self.bot, allowed_updates=["message", "callback_query", "my_chat_member"]
        )

    def format_filter_status(self, filter_data: Optional[dict]) -> str:
        """
        Format filter status message

        Args:
            filter_data (Optional[dict]): Данные фильтра

        Returns:
            str: Отформатированное сообщение о статусе фильтра
        """
        if not filter_data:
            return (
                f"❌ В данный момент фильтры не установлены\n\n"
                f"Чтобы установить фильтр для поиска жилья нажмите кнопку - {Buttons.SET_FILTER}"
            )

        # Логируем данные фильтра для отладки
        logging.info(f"Filter data: {filter_data}")

        # Город теперь хранится в русском написании
        city = filter_data.get("city")
        city = city.capitalize() if city else "Все города"

        # Получаем тип съёма
        rental_type = filter_data.get("rental_type")
        rental_type_display = (
            RentalTypes.get_display_preview_name(rental_type)
            if rental_type
            else "Не указан"
        )

        filter_text = "📋 Текущие фильтры:\n\n"
        filter_text += f"🏠 Тип съёма: {rental_type_display}\n"

        # Разные поля в зависимости от типа фильтра
        if rental_type == RentalTypes.ROOM_SHARING:
            # Для фильтра подселения
            gender = filter_data.get("gender")
            logging.info(f"Gender value: {gender}")

            # Получаем отображаемое имя для пола
            if gender == GenderTypes.MALE:
                gender_display = "👨 Мужчина"
            elif gender == GenderTypes.FEMALE:
                gender_display = "👩 Женщина"
            else:
                gender_display = "Не указан"

            # Получаем отображаемое имя для предпочтений по соседям
            roommate_preference = filter_data.get("roommate_preference")
            logging.info(f"Roommate preference value: {roommate_preference}")

            if roommate_preference == GenderTypes.PREFER_MALE:
                preference_display = "👨 Мужчины"
            elif roommate_preference == GenderTypes.PREFER_FEMALE:
                preference_display = "👩 Женщины"
            elif roommate_preference == GenderTypes.NO_PREFERENCE:
                preference_display = "👨👩 Не имеет значения"
            else:
                preference_display = "Не указаны"

            max_price = filter_data.get("max_price")

            filter_text += f"👤 Ваш пол: {gender_display}\n"
            filter_text += f"👥 Предпочтения по соседям: {preference_display}\n"
            filter_text += f"🏙 Город: {city}\n"

            price_text = "💰 Цена: Любая цена\n"
            if max_price:
                price_text = f"💰 Цена: до {int(max_price)} тг\n"

            filter_text += price_text
        else:
            # Для фильтра поиска жилья целиком
            rooms = filter_data.get("rooms", "Любое количество")
            min_price = filter_data.get("min_price", None)
            max_price = filter_data.get("max_price", None)
            min_square = filter_data.get("min_square", "Без минимума")

            filter_text += f"🏙 Город: {city}\n"

            if rooms:
                filter_text += f"🏠 Комнаты: {', '.join(map(str, rooms))}\n"

            if max_price and min_price:
                filter_text += f"💰 Цена: {min_price} - {max_price} тг\n"
            elif min_price:
                filter_text += f"💰 Цена: от {min_price} тг\n"
            elif max_price:
                filter_text += f"💰 Цена: до {max_price} тг\n"
            else:
                filter_text += "💰 Цена: Любая цена\n"

            if min_square:
                min_square_to_show = min_square
                if int(min_square_to_show) == min_square:
                    min_square_to_show = int(min_square_to_show)
                filter_text += f"📏 Площадь: от {min_square_to_show} м²\n"

            else:
                filter_text += "📏 Площадь: Любая площадь\n"

        filter_text += (
            f"\nЕсли вы хотите изменить фильтр нажмите на кнопку '{Buttons.SET_FILTER}'"
        )
        return filter_text

    async def handle_gender(self, message: types.Message, state: FSMContext) -> None:
        """
        Обработчик выбора пола для фильтра подселения

        Args:
            message (types.Message): Сообщение от пользователя
            state (FSMContext): Контекст состояния
        """
        # Проверяем на отмену с учетом эмодзи
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return
        gender_type_by_display = GenderTypes.get_gender_name_by_display(message.text)

        # Проверяем выбор пола с учетом эмодзи
        if gender_type_by_display == GenderTypes.MALE:
            gender_value = GenderTypes.MALE
        elif gender_type_by_display == GenderTypes.FEMALE:
            gender_value = GenderTypes.FEMALE
        else:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Пожалуйста, выберите пол из предложенных вариантов.",
                get_gender_keyboard(),
            )
            return

        await state.update_data(gender=gender_value)
        await state.set_state(RoommateFilterStates.setting_roommate_preference)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Укажите предпочтения по соседям:",
            get_roommate_preference_keyboard(),
        )

    async def handle_roommate_preference(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """
        Обработчик выбора предпочтений по соседям

        Args:
            message (types.Message): Сообщение от пользователя
            state (FSMContext): Контекст состояния
        """
        # Проверяем на отмену с учетом эмодзи
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        # Проверяем выбор предпочтений с учетом эмодзи
        if message.text == GenderTypes.PREFER_MALE:
            preference_value = GenderTypes.PREFER_MALE
        elif message.text == GenderTypes.PREFER_FEMALE:
            preference_value = GenderTypes.PREFER_FEMALE
        elif message.text == GenderTypes.NO_PREFERENCE:
            preference_value = GenderTypes.NO_PREFERENCE
        else:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Пожалуйста, выберите предпочтения из предложенных вариантов.",
                get_roommate_preference_keyboard(),
            )
            return

        await state.update_data(roommate_preference=preference_value)
        await state.set_state(RoommateFilterStates.setting_city)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Выберите город для поиска подселения:",
            get_roommate_city_keyboard(),
        )

    async def handle_roommate_city(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """
        Обработчик выбора города для фильтра подселения

        Args:
            message (types.Message): Сообщение от пользователя
            state (FSMContext): Контекст состояния
        """
        # Проверяем на отмену с учетом эмодзи
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        # Получаем название города без эмодзи
        city_text = CityTypes.get_city_name_from_emoji(message.text)

        if not city_text:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Пожалуйста, выберите город из предложенных вариантов.",
                get_roommate_city_keyboard(),
            )
            return

        # Сохраняем русское название города в нижнем регистре
        city_lower = city_text.lower()
        await state.update_data(
            city=city_lower,  # Сохраняем русское название города
            city_display=city_text,  # Для отображения пользователю
        )

        await state.set_state(RoommateFilterStates.setting_max_price)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            (
                "Введите максимальную цену в тенге.\n"
                "Например:\n"
                "`100000` - до 100 000 тг\n"
                "`150000` - до 150 000 тг\n\n"
                "Нажмите на пример, чтобы скопировать его.\n"
                f"Для пропуска этого шага нажмите '{Buttons.SKIP_FILTER}'"
            ),
            get_filter_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def handle_roommate_max_price(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """
        Обработчик установки максимальной цены для фильтра подселения

        Args:
            message (types.Message): Сообщение от пользователя
            state (FSMContext): Контекст состояния
        """
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.SKIP_FILTER:
            await state.update_data(max_price=None)
        else:
            try:
                max_price = float(message.text.replace(" ", ""))
                await state.update_data(max_price=max_price)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot, message.chat.id, "Неверный формат. Введите число."
                )
                return

        # Показываем текущие настройки фильтра подселения
        data = await state.get_data()

        # Подготовка данных для превью
        gender = data.get("gender", "Не указан")
        roommate_preference = data.get("roommate_preference", "Не указаны")
        city_display = data.get("city_display") or "Любой"
        max_price = data.get("max_price")

        price_display = "Любая"
        if max_price:
            price_display = f"до {int(max_price)} тг"

        filter_preview = (
            "📋 Проверьте настройки фильтра подселения:\n\n"
            f"🏠 Тип съёма: {RentalTypes.get_display_name(RentalTypes.ROOM_SHARING)}\n"
            f"👤 Ваш пол: {GenderTypes.get_gender_display_name(gender)}\n"
            f"👥 Предпочтения по соседям: {roommate_preference}\n"
            f"🏙 Город: {city_display}\n"
            f"💰 Цена: {price_display}\n\n"
            "Создать фильтр с этими настройками?"
        )

        await state.set_state(RoommateFilterStates.confirming_filters)
        await self.message_manager.send_message(
            self.bot, message.chat.id, filter_preview, get_confirm_keyboard()
        )

    async def process_roommate_confirmation(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """
        Обработка подтверждения создания фильтра подселения

        Args:
            message (types.Message): Сообщение от пользователя
            state (FSMContext): Контекст состояния
        """
        if message.text == Buttons.CANCEL:
            await self.cancel_filter_setup(message, state)
            return

        if message.text == Buttons.CREATE_FILTER:
            data = await state.get_data()
            user_id = message.from_user.id

            # Логируем данные для отладки
            logging.info(f"Roommate filter data before saving: {data}")
            logging.info(f"Gender: {data.get('gender')}")
            logging.info(f"Roommate preference: {data.get('roommate_preference')}")

            try:
                # Сначала удаляем старый фильтр
                try:
                    requests.delete(f"{SCRAPER_SERVICE_URL}/users/{user_id}/filters")
                except Exception as e:
                    logging.warning(f"Failed to delete old filter: {e}")

                # Подготовка данных для сохранения
                filter_data = {
                    "user_id": user_id,
                    "city": data.get("city"),
                    "gender": data.get("gender"),
                    "roommate_preference": data.get("roommate_preference"),
                    "max_price": data.get("max_price"),
                    "rental_type": RentalTypes.ROOM_SHARING,
                }

                logging.info(f"Sending filter data to API: {filter_data}")

                # Сохраняем новый фильтр в базу данных
                response = requests.post(
                    f"{SCRAPER_SERVICE_URL}/users/filters",
                    json=filter_data,
                )

                if response.ok:
                    logging.info(
                        f"API response: {response.status_code} - {response.text}"
                    )

                    # Проверяем, что API вернуло корректный ответ
                    try:
                        api_response = response.json()
                        logging.info(f"API response JSON: {api_response}")
                    except Exception as e:
                        logging.warning(f"Failed to parse API response as JSON: {e}")
                else:
                    logging.error(
                        f"Failed to save filter: {response.status_code} - {response.text}"
                    )
                    await self.message_manager.send_message(
                        bot=self.bot,
                        chat_id=message.chat.id,
                        text="⚠️ Не удалось сохранить фильтры. Пожалуйста, попробуйте позже.",
                        reply_markup=get_main_keyboard(),
                    )
                    return

                # Обновляем локальный фильтр
                user_filters.set_filter(
                    user_id,
                    city=data.get("city"),
                    gender=data.get("gender"),
                    roommate_preference=data.get("roommate_preference"),
                    max_price=data.get("max_price"),
                    rental_type=RentalTypes.ROOM_SHARING,
                )

                # Проверяем, что фильтр сохранился локально
                local_filter = user_filters.get_filter(user_id)
                logging.info(f"Local filter after saving: {local_filter}")

                # Отправляем сообщение об успешном создании фильтра
                await self.message_manager.send_message(
                    bot=self.bot,
                    chat_id=message.chat.id,
                    text="✅ Фильтр подселения успешно создан!\nВы будете получать уведомления о новых объявлениях, соответствующих вашему фильтру.",
                    reply_markup=get_main_keyboard(),
                )

            except Exception as e:
                logging.error(f"Error saving roommate filter: {e}")
                await self.message_manager.send_message(
                    bot=self.bot,
                    chat_id=message.chat.id,
                    text="⚠️ Произошла ошибка при сохранении фильтров.",
                    reply_markup=get_main_keyboard(),
                )

            await state.clear()


def get_gender_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Получить клавиатуру для выбора пола

    Returns:
        types.ReplyKeyboardMarkup: Клавиатура с кнопками выбора пола
    """
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=GenderTypes.get_gender_display_name(GenderTypes.MALE)
                )
            ],
            [
                types.KeyboardButton(
                    text=GenderTypes.get_gender_display_name(GenderTypes.FEMALE)
                )
            ],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


def get_roommate_preference_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Получить клавиатуру для выбора предпочтений по соседям

    Returns:
        types.ReplyKeyboardMarkup: Клавиатура с кнопками выбора предпочтений
    """
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=GenderTypes.PREFER_MALE)],
            [types.KeyboardButton(text=GenderTypes.PREFER_FEMALE)],
            [types.KeyboardButton(text=GenderTypes.NO_PREFERENCE)],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )


def get_roommate_city_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Получить клавиатуру для выбора города для подселения

    Returns:
        types.ReplyKeyboardMarkup: Клавиатура с кнопками выбора города
    """
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=CityTypes.ALMATY)],
            [types.KeyboardButton(text=CityTypes.ASTANA)],
            [types.KeyboardButton(text=Buttons.CANCEL)],
        ],
        resize_keyboard=True,
    )

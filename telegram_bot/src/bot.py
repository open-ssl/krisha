from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from filters import UserFilters
import requests
import os
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage
from typing import Optional
from message_manager import MessageManager
import logging

load_dotenv()

user_filters = UserFilters()

class FilterStates(StatesGroup):
    """States for filter setup process"""
    setting_city = State()
    setting_rooms = State()
    setting_min_price = State()
    setting_max_price = State()
    confirming_filters = State()


def get_filter_keyboard() -> types.ReplyKeyboardMarkup:
    """Get keyboard with cancel and skip buttons"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Пропуск фильтра")],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )

def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    """Get main menu keyboard"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Искать")],
            [types.KeyboardButton(text="Установить фильтр"), 
             types.KeyboardButton(text="Автор")]
        ],
        resize_keyboard=True
    )

def get_confirm_keyboard() -> types.ReplyKeyboardMarkup:
    """Get confirmation keyboard"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Создать фильтр")],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )

def get_author_keyboard() -> types.InlineKeyboardMarkup:
    """Get inline keyboard with author profile link"""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Перейти в профиль автора",
                    url=os.getenv("AUTHOR_URL")
                )
            ]
        ]
    )
    return keyboard


def format_filter_status(filter_data: Optional[dict]) -> str:
    """Format filter status message"""
    if not filter_data:
        return "Фильтры не установлены"
        
    city = filter_data.get('city', 'Все города')
    rooms = filter_data.get('rooms', 'Любое количество')
    min_price = filter_data.get('min_price', 'Без минимума')
    max_price = filter_data.get('max_price', 'Без максимума')
    
    return f"Текущие фильтры:\nГород: {city}\nКомнаты: {rooms}\nЦена: от {min_price} до {max_price}"


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
        self.message_manager = MessageManager()
        self.setup_handlers()

    def setup_handlers(self) -> None:
        """Setup bot command handlers"""
        # Команды
        self.dp.message.register(self.start_handler, Command(commands=["start"]))
        
        # Обработчики кнопок главного меню
        self.dp.message.register(self.search_handler, F.text == "Искать")
        self.dp.message.register(self.author_handler, F.text == "Автор")
        self.dp.message.register(self.start_filter_setup, F.text == "Установить фильтр")
        
        # Обработчики состояний фильтров
        self.dp.message.register(self.process_city, StateFilter(FilterStates.setting_city))
        self.dp.message.register(self.process_rooms, StateFilter(FilterStates.setting_rooms))
        self.dp.message.register(self.process_min_price, StateFilter(FilterStates.setting_min_price))
        self.dp.message.register(self.process_max_price, StateFilter(FilterStates.setting_max_price))
        self.dp.message.register(self.process_confirmation, StateFilter(FilterStates.confirming_filters))

        # Добавляем обработчик изменения статуса бота
        self.dp.my_chat_member.register(self.handle_bot_blocked)

    async def start_handler(self, message: types.Message) -> None:
        """Handle /start command"""
        user = message.from_user
        
        # Регистрируем пользователя в базе
        try:
            response = requests.post(
                f"{os.getenv('SCRAPER_SERVICE_URL')}/users",
                json={
                    "user_id": user.id,
                    "first_name": user.first_name if user.first_name else None,
                    "last_name": user.last_name if user.last_name else None,
                    "is_active": True
                }
            )
            if not response.ok:
                logging.error(f"Failed to register user: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Error registering user: {e}")
        
        user_filter = user_filters.get_filter(user.id)
        filter_status = format_filter_status(user_filter)
        
        # Формируем приветственное сообщение с именем пользователя, если оно есть
        greeting = f"Привет{' ' + user.first_name if user.first_name else ''}! "
        greeting += "Я помогу найти квартиру на Krisha.kz\n\n"
        greeting += filter_status
        
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            greeting,
            get_main_keyboard()
        )

    async def start_filter_setup(self, message: types.Message, state: FSMContext) -> None:
        """Start filter setup process"""
        await state.clear()
        await state.set_state(FilterStates.setting_city)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Введите город (например: almaty, nur-sultan, shymkent, karaganda)\n\n"
            "❗ При пропуске этого фильтра поиск будет осуществляться по всем городам Казахстана",
            get_filter_keyboard()
        )

    async def process_city(self, message: types.Message, state: FSMContext) -> None:
        """Process city input"""
        if message.text == "Отмена":
            await self.cancel_filter_setup(message, state)
            return
            
        if message.text == "Пропуск фильтра":
            await state.update_data(city=None)
        else:
            await state.update_data(city=message.text.lower())
            
        await state.set_state(FilterStates.setting_rooms)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Введите количество комнат через запятую (например: 1,2,3)\n\n"
            "❗ При пропуске этого фильтра будут показаны квартиры с любым количеством комнат",
            get_filter_keyboard()
        )

    async def process_rooms(self, message: types.Message, state: FSMContext) -> None:
        """Process rooms input"""
        if message.text == "Отмена":
            await self.cancel_filter_setup(message, state)
            return
            
        if message.text == "Пропуск фильтра":
            await state.update_data(rooms=None)
        else:
            try:
                rooms = [int(x.strip()) for x in message.text.split(",")]
                await state.update_data(rooms=rooms)
            except ValueError:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "Неверный формат. Введите числа через запятую (например: 1,2,3):",
                    get_filter_keyboard()
                )
                return
                
        await state.set_state(FilterStates.setting_min_price)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Введите минимальную цену тенге(₸), например: 100000\n\n"
            "❗ При пропуске этого фильтра минимальная цена не будет учитываться",
            get_filter_keyboard()
        )

    async def process_min_price(self, message: types.Message, state: FSMContext) -> None:
        """Process minimum price input"""
        if message.text == "Отмена":
            await self.cancel_filter_setup(message, state)
            return
            
        if message.text == "Пропуск фильтра":
            await state.update_data(min_price=None)
        else:
            try:
                await state.update_data(min_price=float(message.text))
            except ValueError:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "Неверный формат. Введите число:",
                    get_filter_keyboard()
                )
                return
                
        await state.set_state(FilterStates.setting_max_price)
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "Введите максимальную цену в тенге(₸), например: 500000\n\n"
            "❗ При пропуске этого фильтра максимальная цена не будет учитываться",
            get_filter_keyboard()
        )

    async def process_max_price(self, message: types.Message, state: FSMContext) -> None:
        """Process maximum price input"""
        if message.text == "Отмена":
            await self.cancel_filter_setup(message, state)
            return
            
        if message.text == "Пропуск фильтра":
            await state.update_data(max_price=None)
        else:
            try:
                await state.update_data(max_price=float(message.text))
            except ValueError:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "Неверный формат. Введите число:",
                    get_filter_keyboard()
                )
                return
                
        await state.set_state(FilterStates.confirming_filters)
        await self.show_filter_preview(message, state)

    async def show_filter_preview(self, message: types.Message, state: FSMContext) -> None:
        """Show filter preview"""
        data = await state.get_data()
        preview = "Проверьте настройки фильтров:\n\n"
        preview += f"🏙 Город: {data.get('city', 'Все города')}\n"
        preview += f"🏠 Комнаты: {data.get('rooms', 'Любое количество')}\n"
        preview += f"💰 Минимальная цена: {data.get('min_price', 'Без минимума')}\n"
        preview += f"💰 Максимальная цена: {data.get('max_price', 'Без максимума')}\n\n"
        preview += "Создать фильтр с этими настройками?"
        
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            preview,
            get_confirm_keyboard()
        )

    async def process_confirmation(self, message: types.Message, state: FSMContext) -> None:
        """Process filter confirmation"""
        if message.text == "Отмена":
            await self.cancel_filter_setup(message, state)
            return
            
        if message.text == "Создать фильтр":
            data = await state.get_data()
            user_filters.set_filter(
                message.from_user.id,
                city=data.get('city'),
                rooms=data.get('rooms'),
                min_price=data.get('min_price'),
                max_price=data.get('max_price')
            )
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "✅ Фильтры успешно установлены!",
                get_main_keyboard()
            )
            await state.clear()

    async def cancel_filter_setup(self, message: types.Message, state: FSMContext) -> None:
        """Cancel filter setup"""
        await state.clear()
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "❌ Настройка фильтров отменена",
            get_main_keyboard()
        )

    async def search_handler(self, message: types.Message) -> None:
        """Handle search command"""
        user_filter = user_filters.get_filter(message.from_user.id)
        if not user_filter:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                "Сначала установите фильтры!",
                get_main_keyboard()
            )
            return

        try:
            response = requests.post(
                f"http://localhost:{os.getenv('SCRAPER_SERVICE_PORT')}/apartments/filter",
                json=user_filter
            )
            apartments = response.json()
            
            if not apartments:
                await self.message_manager.send_message(
                    self.bot,
                    message.chat.id,
                    "Квартир по вашим критериям не найдено",
                    get_main_keyboard()
                )
                return
                
            result_message = "Найденные квартиры:\n\n"
            for apt in apartments:
                # Формируем адресную часть
                location_parts = []
                if apt.get('district'):
                    location_parts.append(f"р-н {apt['district']}")
                if apt.get('street'):
                    location_parts.append(apt['street'])
                if apt.get('complex_name'):
                    location_parts.append(f"(ЖК {apt['complex_name']})")
                
                location = ', '.join(filter(None, location_parts))
                
                result_message += (
                    f"🏠 {apt['rooms']}-комн. {location}, "
                    f"*{apt['price']} тг*\n"
                    f"{apt['url']}\n\n"
                )
                
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                result_message,
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            await self.message_manager.send_message(
                self.bot,
                message.chat.id,
                f"Произошла ошибка при поиске: {str(e)}",
                get_main_keyboard()
            )

    async def author_handler(self, message: types.Message) -> None:
        """Handle author command"""
        await self.message_manager.send_message(
            self.bot,
            message.chat.id,
            "👨‍💻 Автор бота:",
            reply_markup=get_author_keyboard()
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
                f"{os.getenv('SCRAPER_SERVICE_URL')}/users",
                json={
                    "user_id": user.id,
                    "first_name": user.first_name if user.first_name else None,
                    "last_name": user.last_name if user.last_name else None,
                    "is_active": is_active
                }
            )
            if not response.ok:
                logging.error(f"Failed to update user block status: {response.status_code} - {response.text}")
                
            # Если пользователь разблокировал бота, отправляем приветственное сообщение
            if is_active:
                await self.message_manager.send_message(
                    self.bot,
                    user.id,
                    f"С возвращением{' ' + user.first_name if user.first_name else ''}! "
                    "Я продолжу отправлять вам уведомления о новых квартирах.",
                    get_main_keyboard()
                )
                
        except Exception as e:
            logging.error(f"Error updating user block status: {e}")

    async def start(self) -> None:
        """Start the bot with polling"""
        await self.dp.start_polling(
            self.bot,
            allowed_updates=["message", "callback_query"]
        ) 
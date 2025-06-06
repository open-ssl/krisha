import asyncio
import logging

from aiogram import Bot
from dotenv import load_dotenv

from bot import KrishaBot
from env import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID
from message_manager import MessageManager
from notifications import NotificationHandler


async def main():
    """Main function"""
    load_dotenv()

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message_manager = MessageManager(admin_id=TELEGRAM_ADMIN_ID)
    notification_handler = NotificationHandler(message_manager, bot)

    # Подключаемся к Redis перед запуском
    await notification_handler.connect()

    krisha_bot = KrishaBot(TELEGRAM_BOT_TOKEN)

    try:
        await asyncio.gather(krisha_bot.start(), notification_handler.start())
    except Exception as e:
        logging.error(f"Error running bot: {e}")
    finally:
        await notification_handler.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

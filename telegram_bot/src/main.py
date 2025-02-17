from bot import KrishaBot
from notifications import NotificationHandler
import os
from dotenv import load_dotenv
import asyncio
import logging

load_dotenv()

async def main():
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    # Создаем и запускаем бота
    bot = KrishaBot(os.getenv("TELEGRAM_BOT_TOKEN"))
    
    # Создаем и запускаем обработчик уведомлений
    notification_handler = NotificationHandler(
        message_manager=bot.message_manager,
        bot=bot.bot
    )
    
    # Запускаем оба процесса параллельно
    await asyncio.gather(
        bot.start(),
        notification_handler.start()
    )

if __name__ == "__main__":
    asyncio.run(main()) 
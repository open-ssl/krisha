import asyncio

from telethon import TelegramClient
from src.env import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER, TELEGRAM_ADMIN_ID


async def main():
    telegram_client = TelegramClient(
        "telegram_scraper_session2",
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
        # loop=telethon_loop,
    )

    try:
        await telegram_client.start(
            phone=TELEGRAM_PHONE_NUMBER,
        )
    except Exception as e:
        stas = 1

    dialogs = await telegram_client.get_dialogs(5)


if __name__ == '__main__':
    # city = "алматы"
    # gender = "female"
    # preference = "🤝 Не важно"
    # max_price = 100000.0
    # stas = get_unseen_sharing_apartments(
    #     user_id=TELEGRAM_ADMIN_ID,
    #     city = city,
    #     max_price = max_price,
    #     gender = gender,
    #     roommate_preference = preference,
    # )
    asyncio.run(main())


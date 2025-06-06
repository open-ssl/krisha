import asyncio
import logging
import threading
import time

import schedule
import uvicorn

from api import app
from src.database import cleanup_old_entries
from src.env import SCRAPER_SERVICE_PORT
from src.scraper import scraping_job
from src.telegram.telegram_scraper import telegram_scraping_job
from src.telegram.verification_service import initialize_broker


# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Глобальная переменная для хранения цикла событий
event_loop = None

# Глобальная переменная для хранения брокера
broker = None

# Флаг для отслеживания первого запуска скрапинга Telegram
first_telegram_scraping_run = True


async def run_telegram_scraping():
    """
    Запускает задачу скрапинга Telegram в основном цикле событий.
    """
    global first_telegram_scraping_run

    try:
        # Если это первый запуск, добавляем задержку для инициализации
        if first_telegram_scraping_run:
            first_telegram_scraping_run = False

        await telegram_scraping_job()
    except Exception as e:
        logging.error(f"Ошибка при выполнении telegram_scraping_job: {e}")


def run_async_in_thread(coro_func):
    """
    Запускает асинхронную функцию в основном цикле событий.

    Args:
        coro_func: Асинхронная функция для запуска
    """
    global event_loop

    if event_loop and event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro_func(), event_loop)
        logging.info(f"Запущена задача {coro_func.__name__} в основном цикле событий")
    else:
        logging.error(
            f"Не удалось запустить {coro_func.__name__}: цикл событий не запущен или недоступен"
        )


@app.on_event("startup")
async def startup_event():
    """
    Выполняется при запуске приложения.
    """
    global event_loop, broker

    # Сохраняем текущий цикл событий
    event_loop = asyncio.get_running_loop()

    # Инициализируем брокер RabbitMQ
    broker = await initialize_broker()
    await broker.start()

    # Запускаем начальные задачи
    try:
        # Запускаем другие задачи очистки
        cleanup_old_entries()
        logging.info("Начальные задачи выполнены успешно")
    except Exception as e:
        logging.error(f"Ошибка при выполнении начальных задач: {e}")

    # Настраиваем расписание задач
    logging.info("Настройка расписания задач")

    # Планируем регулярное выполнение
    schedule.every(90).seconds.do(lambda: run_async_in_thread(run_telegram_scraping))
    schedule.every(1).minutes.do(lambda: scraping_job(broker))
    schedule.every(1).days.do(cleanup_old_entries)

    logging.info("Scheduler is running, next job is scheduled")

    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Логируем информацию о следующем запланированном задании
    next_job = schedule.next_run()
    if next_job:
        logging.info("Scheduler is running, next job is scheduled")
        logging.info(f"Next scheduled job at: {next_job}")
    else:
        logging.warning("No scheduled jobs found")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Выполняется при остановке приложения.
    """
    global broker

    # Останавливаем брокер
    if broker:
        await broker.close()

    logging.info("Scraper service stopped")


def run_scheduler():
    """
    Функция для запуска планировщика задач в отдельном потоке.
    """
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SCRAPER_SERVICE_PORT)

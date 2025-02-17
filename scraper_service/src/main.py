import schedule
import time
import uvicorn
from scraper import KrishaScraper
from database import save_apartment, cleanup_old_entries
from api import app
import threading
from dotenv import load_dotenv
import os

load_dotenv()

def scraping_job():
    """Periodic scraping job"""
    scraper = KrishaScraper()
    # Пример параметров поиска
    apartments = scraper.get_apartments(
        city="almaty",
        rooms=[2, 3],
        max_price=400000
    )
    
    for apartment in apartments:
        save_apartment(
            url=apartment['url'],
            price=apartment['price'],
            rooms=apartment['rooms'],
            city=apartment['city']
        )
    
    cleanup_old_entries()

def run_scheduler():
    """Run scheduler for periodic tasks"""
    schedule.every(10).seconds.do(scraping_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Запускаем FastAPI сервер
    port = int(os.getenv("SCRAPER_SERVICE_PORT", 8088))
    uvicorn.run("api:app", host="0.0.0.0", port=port) 
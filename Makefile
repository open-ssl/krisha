.PHONY: install-scraper install-bot run-scraper run-bot docker-build docker-up docker-down docker-logs docker-restart docker-clean docker-rebuild docker-init docker-rebuild-services

# Команды для локальной разработки
install-scraper:
	cd scraper_service && poetry install

install-bot:
	cd telegram_bot && poetry install

run-scraper:
	cd scraper_service && poetry run python src/main.py

run-bot:
	cd telegram_bot && poetry run python src/main.py

# Команды форматирования
format-telegram:
	@cd telegram_bot && poe format

format-scraper:
	@cd scraper_service && poe format

format: format-telegram format-scraper

# Команды для Docker
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-restart:
	docker compose restart

# Команды для очистки
docker-clean:
	docker compose down -v
	docker system prune -f

# Полезные комбинации команд
docker-rebuild: docker-down docker-build docker-up docker-logs

# Команда для первого запуска
docker-init: docker-build docker-up docker-logs

# Команда для пересборки только сервисов без инфраструктуры
docker-rebuild-services:
	docker compose stop scraper bot notification_service
	docker compose rm -f scraper bot notification_service
	docker compose build scraper bot notification_service
	docker compose up -d scraper bot notification_service
	docker compose logs -f scraper bot notification_service

docker-rebuild-services-server:
	docker compose stop scraper bot notification_service
	docker compose rm -f scraper bot notification_service
	docker compose build scraper bot notification_service
	docker compose up -d scraper bot notification_service

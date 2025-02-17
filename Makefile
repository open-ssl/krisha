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

# Команды для Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

# Команды для очистки
docker-clean:
	docker-compose down -v
	docker system prune -f

# Полезные комбинации команд
docker-rebuild: docker-down docker-build docker-up docker-logs

# Команда для первого запуска
docker-init: docker-build docker-up docker-logs

# Команда для пересборки только сервисов без инфраструктуры
docker-rebuild-services:
	docker-compose stop scraper bot
	docker-compose rm -f scraper bot
	docker-compose build scraper bot
	docker-compose up -d scraper bot
	docker-compose logs -f scraper bot 
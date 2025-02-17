#!/bin/sh

# Запускаем миграции
echo "Running database migrations..."
poetry run alembic upgrade head

# Запускаем основное приложение
echo "Starting application..."
poetry run python src/main.py 
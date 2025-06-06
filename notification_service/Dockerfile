FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем poetry
RUN pip install poetry==1.7.1

# Копируем только файлы для установки зависимостей
COPY pyproject.toml poetry.lock* ./

# Устанавливаем зависимости
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-ansi

# Копируем остальной код приложения
COPY . .

# Запускаем приложение
CMD ["python", "src/main.py"]
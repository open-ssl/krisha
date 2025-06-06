import asyncio
import json
import logging
import random
import re

import httpx

from src.env import TOGETHER_API_KEYS


def extract_data_from_atypical_response(result):
    """
    Извлекает данные из нетипичной схемы ответа модели.

    Args:
        result (str): Ответ модели для анализа

    Returns:
        dict: Извлеченные данные или None, если извлечение не удалось
    """
    try:
        # Ищем ключи в формате $is_offer, $montly_price и т.д.
        parsed_data = {}
        keys = [
            "is_offer",
            "is_roommate_offer",
            "is_rental_offer",
            "montly_price",
            "preferred_gender",
            "location",
            "contact",
        ]

        for key in keys:
            pattern = rf"\${key}\s*=\s*['\"]?([^'\";]+)['\"]?;"
            match = re.search(pattern, result)
            if match:
                value = match.group(1).strip()
                # Преобразуем строковые true/false в булевы значения
                if value.lower() == "true":
                    parsed_data[key] = True
                elif value.lower() == "false":
                    parsed_data[key] = False
                elif key in ["location", "contact"] and value.lower() == "null":
                    parsed_data[key] = None
                else:
                    parsed_data[key] = value

        # Если удалось извлечь хотя бы некоторые ключи, используем их
        if parsed_data:
            logging.info("Удалось извлечь данные из нетипичной схемы ответа")
            # Заполняем недостающие ключи значениями по умолчанию
            default_values = get_default_response()
            for key, default_value in default_values.items():
                if key not in parsed_data:
                    parsed_data[key] = default_value

            return parsed_data
        return None
    except Exception as e:
        logging.error(f"Ошибка при попытке извлечь данные из нетипичной схемы: {e}")
        return None


def get_default_response():
    """
    Возвращает словарь с значениями по умолчанию для ответа.

    Returns:
        dict: Словарь с значениями по умолчанию
    """
    return {
        "is_offer": False,
        "is_roommate_offer": False,
        "is_rental_offer": False,
        "montly_price": "",
        "preferred_gender": "no",
        "location": None,
        "contact": None,
        "city": None,
    }


async def analyze_message(message_text):
    """
    Асинхронно анализирует текст сообщения и определяет, является ли оно объявлением об аренде.

    Args:
        message_text (str): Текст сообщения для анализа

    Returns:
        dict: Результат анализа в виде словаря с параметрами объявления
    """
    # Формируем промпт для анализа
    prompt_text = (
        f"""
    Определи параметры поста:
    {message_text}
    """
        + """
    Ты должен вернуть в ответе **ТОЛЬКО ОДИН** JSON-объект как строку:
    {
        "is_offer": true/false,  (Является ли этот текст предложением аренды или подселения в квартиру, кто-то ищет человека в квартиру? (true/false) (ответ одним словом))
        "is_roommate_offer": true/false,  (Это объявление о поиске соседа для подселения или совместного проживания? (true/false) (ответ одним словом))
        "is_rental_offer": true/false,  (Это объявление о долгосрочной аренде квартиры целиком для одного человека? (true/false) (ответ одним словом))
        "montly_price": string, (Цена которую предлагают за аренду, число без лишних знаков - например 90000)
        "preferred_gender": "boy"/"girl"/"both"/"no", (Кого ищут (boy (мужской пол), girl (мужской пол), both (пол не важен), no (не указано))? (ответ одним словом))
        "location": "string" или null,  (Указанная локация, если есть иначе None.)
        "contact": "string" или null, (Контакт автора, если есть иначе None. (контакт автора объявления))
        "city": "string" или null, (Город где предлагают квартиру, алмата или астана в нижнем регистре иначе None)
    }
    Не возвращать больше никаких объектов или данных кроме 1 JSON-объекта.
    """
    )

    # Отправляем запрос на анализ
    result = await send_request(prompt_text)

    if not result:
        return get_default_response()

    # Извлекаем JSON из ответа
    try:
        # Находим начало и конец JSON-объекта
        index_start = result.find("{")
        index_finish = result.find("}") + 1  # +1 чтобы включить закрывающую скобку

        if index_start >= 0 and index_finish > index_start:
            json_str = result[index_start:index_finish]
            # Парсим JSON
            return json.loads(json_str)
        else:
            parsed_data = extract_data_from_atypical_response(result)
            if parsed_data:
                return parsed_data

            logging.warning("JSON не найден в ответе модели")
            return get_default_response()
    except Exception as e:
        logging.error(f"Ошибка при парсинге JSON: {e}")
        return get_default_response()


async def send_request(prompt_text):
    """
    Асинхронно отправляет запрос к LLM с ротацией API-ключей.

    Args:
        prompt_text (str): Текст промпта для модели

    Returns:
        str: Ответ модели
    """
    if not TOGETHER_API_KEYS:
        logging.error("API ключи для Together не настроены")
        return None

    # Перемешиваем ключи для равномерного использования
    api_keys = TOGETHER_API_KEYS.copy()
    random.shuffle(api_keys)

    for api_key in api_keys:
        logging.info("Делаем запрос в together")

        try:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                        "prompt": prompt_text,
                        "max_tokens": 100,
                        "temperature": 0.1,
                    }
                    response = await client.post(
                        "https://api.together.xyz/v1/completions",
                        json=payload,
                        headers=headers,
                    )
                    response = response.json()
            except asyncio.TimeoutError:
                logging.error("Запрос к модели превысил время ожидания")
                continue  # Пробуем следующий ключ

            if response and "choices" in response:
                logging.info("Успешный ответ от модели")
                return response["choices"][0]["text"]

        except Exception as e:
            logging.error(f"Ошибка запроса к модели с ключом {api_key[:5]}...: {e}")

        # Асинхронная пауза перед сменой ключа
        await asyncio.sleep(0.5)

    logging.error("Все ключи исчерпаны или не работают")
    return None

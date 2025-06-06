import asyncio
import random
import httpx
from env import TOGETHER_API_KEY1, TOGETHER_API_KEY2
from time import time, sleep


API_KEYS = [
    TOGETHER_API_KEY1,
    TOGETHER_API_KEY2
]

POST_TEXT = """
'Добрый день.\nИщу девушку в изолированную комнату (либо одну, либо двоих) \nКвартира со всеми удобствами, 2х комнатная.\nЖК зодиак, 5этаж \nАвтобусная остановка все рядом, магазины, Атакент, универы и прочее. \nАдрес: Радостовца 158 (грубо говоря Тимирязева-Гагарина).\nПо оплате и прочим вопросам (писать на номер 87473939708)'

"""
# Промпт (пример с объявлением о квартире)
PROMPT_TEXT = f"""
Определи параметры поста:
{POST_TEXT}
""" + """
Ты должен вернуть в ответе **ТОЛЬКО ОДИН** JSON-объект как строку:
{
    "is_offer": true/false,  (Это предложение о сдаче в аренду квартиры или места в квартире? (true/false) (ответ одним словом))
    "is_roommate_offer": true/false,  (Это объявление о поиске соседа для подселения или совместного проживания? (true/false) (ответ одним словом))
    "is_rental_offer": true/false,  (Это объявление о долгосрочной аренде квартиры целиком для одного съёмщика? (true/false) (ответ одним словом))
    "montly_price": string, (Цена которую предлагают за аренду)
    "preferred_gender": "boy"/"girl"/"both"/"no", (Кого ищут (boy (мужской пол), girl (мужской пол), both (пол не важен), no (не указано))? (ответ одним словом))
    "location": "string" или null,  (Указанная локация, если есть иначе None.)
    "contact": "string" или null, (Контакт автора, если есть иначе None. (контакт автора объявления))
}

Не возвращать больше никаких объектов или данных кроме 1 JSON-объекта.
"""


# Функция для отправки запроса с ротацией API-ключей
async def send_request():
    for _ in range(len(API_KEYS)):
        api_key = random.choice(API_KEYS)

        print(f"Используем API-ключ: {api_key}...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                    "prompt": PROMPT_TEXT,
                    "max_tokens": 100,
                    "temperature": 0.1
                }
                response = await client.post(
                    "https://api.together.xyz/v1/completions",
                    json=payload,
                    headers=headers
                )
                response = response.json()

            if response and "choices" in response:
                print("✅ Успешный ответ!")
                return response["choices"][0]["text"]

        except Exception as e:
            print(f"⚠️ Ошибка запроса: {e}")

        sleep(0.5)  # Пауза перед сменой ключа

    return "❌ Все ключи исчерпаны или не работают."


if __name__ == '__main__':
    start_time = time()
    result = asyncio.run(send_request())
    print(f"???? {time() - start_time}")
    print("\n📌 **Результат:**\n", result)
    index_start = result.find("{")
    index_finish = result.find("}")

    import json

    json_object = "{" + result[index_start+1:index_finish] + "}"
    finish_result = json.loads(json_object)


class CityTypes:
    """Города, в которых можно искать подселение"""

    # Базовые константы для городов
    ALMATY = "⛰️ Алматы"
    ASTANA = "🏙️ Астана"

    # Список всех доступных городов для подселения
    AVAILABLE_CITIES = [ALMATY, ASTANA]

    @staticmethod
    def get_city_name_from_emoji(emoji_city: str) -> str:
        """
        Получить название города без эмодзи из названия с эмодзи

        Args:
            emoji_city (str): Название города с эмодзи

        Returns:
            str: Название города без эмодзи
        """
        if emoji_city == CityTypes.ALMATY:
            return "Алматы"
        elif emoji_city == CityTypes.ASTANA:
            return "Астана"
        return ""

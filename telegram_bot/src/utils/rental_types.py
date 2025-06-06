from typing import List


class RentalTypes:
    """
    Класс для хранения типов съёма квартир
    """

    FULL_APARTMENT = "full_apartment"
    ROOM_SHARING = "room_sharing"

    # Названия типов съёма для отображения
    DISPLAY_NAMES = {
        FULL_APARTMENT: "🏠 Жильё целиком",
        ROOM_SHARING: "👥 Подселение",
    }

    DISPLAY_PREVIEW_NAMES = {
        FULL_APARTMENT: "Жильё целиком",
        ROOM_SHARING: "Подселение",
    }

    @classmethod
    def get_display_name(cls, rental_type: str) -> str:
        """
        Получить отображаемое название типа съёма

        Args:
            rental_type (str): Тип съёма на английском

        Returns:
            str: Отображаемое название или 'Неизвестно'
        """
        return cls.DISPLAY_NAMES.get(rental_type, "Неизвестно")

    @classmethod
    def get_display_preview_name(cls, rental_type: str) -> str:
        """
        Получить отображаемое название типа съёма для превью фильтра

        Args:
            rental_type (str): Тип съёма на английском

        Returns:
            str: Отображаемое название или 'Неизвестно'
        """
        return cls.DISPLAY_PREVIEW_NAMES.get(rental_type, "Неизвестно")

    @classmethod
    def get_all_types(cls) -> List[str]:
        """
        Получить список всех типов съёма

        Returns:
            List[str]: Список типов съёма
        """
        return [cls.FULL_APARTMENT, cls.ROOM_SHARING]

    @classmethod
    def is_valid_type(cls, rental_type: str) -> bool:
        """
        Проверить, является ли строка допустимым типом съёма

        Args:
            rental_type (str): Тип съёма для проверки

        Returns:
            bool: True, если тип валидный
        """
        return rental_type in cls.get_all_types()

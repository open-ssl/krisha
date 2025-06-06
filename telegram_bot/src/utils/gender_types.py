from typing import List


class GenderTypes:
    """
    Класс для хранения типов пола и предпочтений по соседям
    """

    # Типы пола
    MALE = "male"
    FEMALE = "female"

    # Предпочтения по соседям
    PREFER_MALE = "👨 Мужчины"
    PREFER_FEMALE = "👩 Женщины"
    NO_PREFERENCE = "🤝 Не важно"

    # Названия типов пола для отображения
    GENDER_DISPLAY_NAMES = {
        MALE: "👨 Мужской",
        FEMALE: "👩 Женский",
    }

    GENDER_NAME_BY_DISPLAY = {
        "👨 Мужской": MALE,
        "👩 Женский": FEMALE,
    }

    # Названия предпочтений по соседям для отображения
    PREFERENCE_DISPLAY_NAMES = {
        PREFER_MALE: "👨 С мужчинами",
        PREFER_FEMALE: "👩 С женщинами",
        NO_PREFERENCE: "👥 Без разницы",
    }

    @classmethod
    def get_gender_display_name(cls, gender_type: str) -> str:
        """
        Получить отображаемое название типа пола

        Args:
            gender_type (str): Тип пола

        Returns:
            str: Отображаемое название или 'Неизвестно'
        """
        return cls.GENDER_DISPLAY_NAMES.get(gender_type, "Неизвестно")

    @classmethod
    def get_gender_name_by_display(cls, gender_type: str) -> str:
        """
        Получить отображаемое название типа пола

        Args:
            gender_type (str): Тип пола

        Returns:
            str: Отображаемое название или 'Неизвестно'
        """
        return cls.GENDER_NAME_BY_DISPLAY.get(gender_type, "Неизвестно")

    @classmethod
    def get_preference_display_name(cls, preference_type: str) -> str:
        """
        Получить отображаемое название предпочтения по соседям

        Args:
            preference_type (str): Тип предпочтения

        Returns:
            str: Отображаемое название или 'Неизвестно'
        """
        return cls.PREFERENCE_DISPLAY_NAMES.get(preference_type, "Неизвестно")

    @classmethod
    def get_all_genders(cls) -> List[str]:
        """
        Получить список всех типов пола

        Returns:
            List[str]: Список типов пола
        """
        return [cls.MALE, cls.FEMALE]

    @classmethod
    def get_all_preferences(cls) -> List[str]:
        """
        Получить список всех предпочтений по соседям

        Returns:
            List[str]: Список предпочтений
        """
        return [cls.PREFER_MALE, cls.PREFER_FEMALE, cls.NO_PREFERENCE]

    @classmethod
    def is_valid_gender(cls, gender_type: str) -> bool:
        """
        Проверить, является ли строка допустимым типом пола

        Args:
            gender_type (str): Тип пола для проверки

        Returns:
            bool: True, если тип валидный
        """
        return gender_type in cls.get_all_genders()

    @classmethod
    def is_valid_preference(cls, preference_type: str) -> bool:
        """
        Проверить, является ли строка допустимым типом предпочтения

        Args:
            preference_type (str): Тип предпочтения для проверки

        Returns:
            bool: True, если тип валидный
        """
        return preference_type in cls.get_all_preferences()

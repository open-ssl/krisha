CITY_MAPPING = {
    "алматы": "almaty",
    "астана": "astana",
    "шымкент": "shymkent",
    "актау": "aktau",
    "актобе": "aktobe",
    "атырау": "atyrau",
    "караганда": "karaganda",
    "кокшетау": "kokshetau",
    "костанай": "kostanay",
    "кызылорда": "kyzylorda",
    "павлодар": "pavlodar",
    "петропавловск": "petropavlovsk",
    "семей": "semey",
    "талдыкорган": "taldykorgan",
    "тараз": "taraz",
    "туркестан": "turkestan",
    "уральск": "uralsk",
    "усть-каменогорск": "ust-kamenogorsk",
    "экибастуз": "ekibastuz",
}


def get_city_name(eng_name: str) -> str:
    """
    Получить русское название города по английскому

    Args:
        eng_name: Английское название города

    Returns:
        str: Русское название города или исходное название, если перевод не найден
    """
    for rus_name, eng in CITY_MAPPING.items():
        if eng == eng_name:
            return rus_name.capitalize()
    return eng_name

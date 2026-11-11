"""Что даёт баллы: достижения, задания недели и ранги. Меняется здесь, без миграций."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    text: str
    points: int
    icon: str  # имя иконки на фронтенде


ACHIEVEMENTS = [
    Achievement("verified", "Свой человек", "Права подтверждены в Рули ID", 100, "shield"),
    Achievement("first_trip", "Первый тег", "Первая поездка завершена", 50, "spark"),
    Achievement("trips_5", "Райтер", "5 поездок", 100, "car"),
    Achievement("trips_20", "Бомбер", "20 поездок", 250, "bolt"),
    Achievement("night_rider", "Ночной райдер", "Поездка между 22:00 и 5:00", 40, "moon"),
    Achievement("early_bird", "Жаворонок", "Старт между 5:00 и 8:00", 30, "sun"),
    Achievement("long_haul", "Дальнобой", "Поездка от 60 минут", 50, "route"),
    Achievement("signature", "Стрит-арт", "Поездка на машине Signature", 30, "seal"),
    Achievement("collector", "Коллекционер", "Поездки в трёх разных классах", 80, "grid"),
    Achievement("detective", "Детектив", "Нашёл новое повреждение на осмотре до поездки", 40, "search"),
    Achievement("crew", "Своя банда", "Друг по твоему коду завершил первую поездку", 0, "user"),
]
ACHIEVEMENTS_BY_CODE = {item.code: item for item in ACHIEVEMENTS}


@dataclass(frozen=True)
class Quest:
    code: str
    title: str
    target: int
    unit: str
    points: int


# Задания обновляются каждый понедельник (неделя по Минску).
QUESTS = [
    Quest("trips_3", "3 поездки за неделю", 3, "поездки", 60),
    Quest("minutes_60", "60 минут за рулём", 60, "мин", 50),
    Quest("night", "Ночная поездка", 1, "поездка", 30),
    Quest("signature", "Прокатись на Signature", 1, "поездка", 30),
]

# Ранги по всем заработанным баллам (траты ранг не снижают) — сленг райтеров.
RANKS = [
    (0, "Той", "Только взял баллончик"),
    (300, "Райтер", "Тебя уже узнают по тегу"),
    (800, "Бомбер", "Город в твоих маршрутах"),
    (2000, "Кинг", "Уважение всей улицы"),
    (4000, "Легенда", "Про тебя рассказывают новичкам"),
]

TRIP_BASE_POINTS = 10
TRIP_POINTS_PER_MINUTES = 2  # +1 балл за каждые 2 минуты в пути
TRIP_MAX_MINUTE_POINTS = 60
REFERRAL_POINTS = 150
POINT_VALUE_BYN = "0.01"  # 100 баллов = 1 BYN
MAX_DISCOUNT_SHARE = "0.30"  # баллами можно оплатить до 30% поездки


def rank_for(earned):
    current = RANKS[0]
    following = None
    for threshold, title, text in RANKS:
        if earned >= threshold:
            current = (threshold, title, text)
        elif following is None:
            following = (threshold, title, text)
    return current, following

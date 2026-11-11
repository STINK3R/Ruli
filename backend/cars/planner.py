"""«Куда едем?» — какую машину выгоднее и быстрее взять для конкретной поездки.

Обычный каршеринг показывает ближайшую машину. Но ближайшая бывает дороже:
другой класс, другой тариф, пакет «Час» не сработает. Планировщик считает
полную цену поездки до точки назначения для нескольких ближайших машин:
пешком до машины + бронь + дорога на машине по лучшему тарифу.
"""

import math
from decimal import Decimal

from django.conf import settings

from .driving import driving_route, driving_table
from .models import Car
from .walking import haversine_m, walking_matrix

CENT = Decimal("0.01")
MAX_TRIP_DISTANCE_M = 120_000


def price_with_label(minutes, tariff):
    """Лучшая цена и как она получилась — клиенту видно, сработал ли пакет."""
    from rentals.services import best_trip_price

    per_minute = Decimal(minutes) * tariff.price_per_minute
    without_day = best_trip_price(minutes, tariff.price_per_minute, tariff.price_per_hour)
    best = best_trip_price(minutes, tariff.price_per_minute, tariff.price_per_hour, tariff.price_per_day)
    if best < without_day:
        label = "пакет «Сутки»"
    elif best < per_minute:
        label = "пакет «Час»"
    else:
        label = "поминутно"
    return best.quantize(CENT), label


def plan_trip(origin, destination, policy=None):
    from rentals.services import WALK_DETOUR_RESERVE, WALK_GET_READY_MINUTES, free_waiting_minutes_for

    if haversine_m(*origin, *destination) > MAX_TRIP_DISTANCE_M:
        return {"options": [], "reason": "Слишком далеко для поездки по городу."}

    cars = Car.objects.filter(status=Car.Status.AVAILABLE).select_related("tariff").prefetch_related("features")
    if policy is not None:
        allowed = [name for name, entry in policy["classes"].items() if entry["allowed"]]
        # Неподтверждённому водителю показываем всё — пусть видит, что откроется после проверки.
        if allowed:
            cars = cars.filter(car_class__in=allowed)
    cars = list(cars)
    if not cars:
        return {"options": [], "reason": "Свободных машин сейчас нет."}

    walks = walking_matrix(origin, [(car.latitude, car.longitude) for car in cars])
    pairs = sorted(zip(cars, walks), key=lambda pair: pair[1]["duration_s"])[: settings.PLANNER_CANDIDATES]
    drives = driving_table([(car.latitude, car.longitude) for car, _ in pairs], destination)
    level = policy["level"] if policy else 0

    options = []
    for (car, walk), drive in zip(pairs, drives):
        trip_minutes = math.ceil(drive["duration_s"] * settings.TRAFFIC_FACTOR / 60) + settings.PARKING_MINUTES
        trip_cost, package = price_with_label(trip_minutes, car.tariff)
        # Бронь по правилу «Честной брони»: пока клиент идёт к машине, ожидание бесплатно.
        free_minutes = free_waiting_minutes_for(walk["duration_s"], level)
        need_minutes = math.ceil(walk["duration_s"] * WALK_DETOUR_RESERVE / 60) + WALK_GET_READY_MINUTES
        paid_waiting = max(0, need_minutes - free_minutes)
        waiting_cost = (Decimal(paid_waiting) * car.tariff.waiting_price_per_minute).quantize(CENT)
        walk_minutes = max(1, math.ceil(walk["duration_s"] / 60))
        car.walk = walk
        options.append(
            {
                "car": car,
                "walk": walk,
                "drive": drive,
                "walk_minutes": walk_minutes,
                "trip_minutes": trip_minutes,
                "trip_cost": trip_cost,
                "package": package,
                "waiting_cost": waiting_cost,
                "total_cost": trip_cost + waiting_cost,
                "arrive_minutes": walk_minutes + trip_minutes,
                "badges": [],
            }
        )

    cheapest = min(options, key=lambda o: (o["total_cost"], o["arrive_minutes"]))
    fastest = min(options, key=lambda o: (o["arrive_minutes"], o["total_cost"]))
    nearest = min(options, key=lambda o: o["walk"]["duration_s"])
    cheapest["badges"].append("cheapest")
    fastest["badges"].append("fastest")
    nearest["badges"].append("nearest")
    options.sort(key=lambda o: (o["total_cost"], o["arrive_minutes"]))

    best_car = cheapest["car"]
    route = driving_route((best_car.latitude, best_car.longitude), destination)
    saving = (nearest["total_cost"] - cheapest["total_cost"]).quantize(CENT)
    return {"options": options, "route": route, "best_car_id": best_car.id, "saving_vs_nearest": saving}

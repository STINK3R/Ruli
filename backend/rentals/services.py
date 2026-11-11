import math
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.verification import access_policy, check_can_rent
from cars.models import Car
from cars.walking import haversine_m, walking_matrix

from .models import Rental

CENT = Decimal("0.01")
WALK_DETOUR_RESERVE = 1.3  # лифт, выход из подъезда, светофоры
WALK_GET_READY_MINUTES = 3
MAX_FREE_WAITING = 25
PLUS_BONUS_MINUTES = 5
PLUS_MAX_FREE_WAITING = 30


# ---------- Деньги ----------

def best_trip_price(minutes, per_minute, per_hour=None, per_day=None) -> Decimal:
    """Самый выгодный для клиента вариант: поминутно, пакеты «час» или «сутки».

    Целые пакеты покрывают основную часть поездки, остаток считается
    поминутно, но не дороже ещё одного пакета.
    """
    best = Decimal(minutes) * per_minute
    if per_hour:
        hours, rest = divmod(minutes, 60)
        best = min(best, hours * per_hour + min(Decimal(rest) * per_minute, per_hour))
    if per_day:
        days, rest = divmod(minutes, 24 * 60)
        rest_price = best_trip_price(rest, per_minute, per_hour)
        best = min(best, days * per_day + min(rest_price, per_day))
    return best


def calculate_trip_cost(rental: Rental) -> Decimal:
    """Поездка по лучшему тарифу; минуты по гарантии Signature не оплачиваются."""
    billable = max(0, rental.duration_minutes - rental.compensation_minutes)
    if billable == 0:
        return Decimal("0.00")
    return best_trip_price(
        billable,
        rental.price_per_minute_at_booking,
        rental.price_per_hour_at_booking,
        rental.price_per_day_at_booking,
    ).quantize(CENT)


def calculate_waiting_cost(rental: Rental, until) -> Decimal:
    """Ожидание: минуты брони сверх бесплатного окна этой брони × цена ожидания."""
    waited = math.ceil((until - rental.reserved_at).total_seconds() / 60)
    paid_minutes = max(0, waited - rental.free_waiting_minutes)
    return (Decimal(paid_minutes) * rental.waiting_price_per_minute_at_booking).quantize(CENT)


# ---------- «Честная бронь» ----------

def free_waiting_minutes_for(walk_seconds, level=0):
    """Бесплатное ожидание по реальному пешему пути: успеть дойти и собраться.

    Не меньше прежних 10 минут и не больше 25; «Допуск Плюс» даёт ещё 5 (до 30).
    """
    if walk_seconds is None:
        minutes = settings.FREE_WAITING_MINUTES
    else:
        minutes = math.ceil(walk_seconds * WALK_DETOUR_RESERVE / 60) + WALK_GET_READY_MINUTES
        minutes = min(max(minutes, settings.FREE_WAITING_MINUTES), MAX_FREE_WAITING)
    if level >= 3:
        minutes = min(minutes + PLUS_BONUS_MINUTES, PLUS_MAX_FREE_WAITING)
    return minutes


def origin_is_plausible(origin, car):
    """Клиент правдоподобно рядом с машиной — только тогда окно считается по пешему пути.

    Издалека — стандартное окно: защита от подмены геопозиции. Одно правило
    и для брони, и для обещания в каталоге.
    """
    if origin is None:
        return False
    return haversine_m(*origin, car.latitude, car.longitude) <= settings.FAIR_BOOKING_MAX_ORIGIN_M


def walk_for_booking(origin, car):
    """Пеший путь для расчёта окна, если клиент правдоподобно рядом с машиной."""
    if not origin_is_plausible(origin, car):
        return None
    return walking_matrix(origin, [(car.latitude, car.longitude)])[0]


def reserve_car(user, car_id: int, origin=None) -> Rental:
    car = Car.objects.select_related("tariff").filter(pk=car_id).first()
    if car is None:
        raise ValidationError("Автомобиль не найден.")
    policy = check_can_rent(user, car)

    # Запрос к OSRM (до 4 с) — строго до блокировки строки машины.
    walk = walk_for_booking(origin, car)
    free_minutes = free_waiting_minutes_for(walk and walk["duration_s"], policy["level"])

    with transaction.atomic():
        if Rental.objects.filter(user=user, status__in=Rental.ACTIVE_STATUSES).exists():
            raise ValidationError("У вас уже есть активная бронь или поездка.")
        car = Car.objects.select_for_update().select_related("tariff").get(pk=car_id)
        if car.status != Car.Status.AVAILABLE:
            raise ValidationError("Автомобиль уже занят — выберите другой.")

        car.status = Car.Status.RESERVED
        car.save(update_fields=["status"])

        return Rental.objects.create(
            user=user,
            car=car,
            status=Rental.Status.RESERVED,
            price_per_minute_at_booking=car.tariff.price_per_minute,
            waiting_price_per_minute_at_booking=car.tariff.waiting_price_per_minute,
            price_per_hour_at_booking=car.tariff.price_per_hour,
            price_per_day_at_booking=car.tariff.price_per_day,
            start_latitude=car.latitude,
            start_longitude=car.longitude,
            free_waiting_minutes=free_minutes,
            walk_duration_s=walk["duration_s"] if walk else None,
            walk_distance_m=walk["distance_m"] if walk else None,
            walk_source=walk["source"] if walk else "",
            client_latitude=origin[0] if origin else None,
            client_longitude=origin[1] if origin else None,
        )


def _require_inspection(rental, kind):
    if not settings.INSPECTIONS_REQUIRED:
        return
    from inspections.models import Inspection

    if not Inspection.objects.filter(rental=rental, kind=kind).exists():
        what = "перед поездкой" if kind == Inspection.Kind.START else "после поездки"
        raise ValidationError({"detail": f"Сначала сделайте осмотр {what}.", "code": "inspection_required"})


def _require_face_check(rental):
    """За руль садится владелец аккаунта: без свежей проверки лица машина не откроется."""
    if not settings.TRIP_FACE_CHECK_REQUIRED:
        return
    check = rental.driver_check
    if check is None or check.status != "passed" or check.created_at < rental.reserved_at:
        raise ValidationError(
            {"detail": "Подтвердите, что за рулём вы: 5 секунд перед камерой.", "code": "face_check_required"}
        )


def start_rental(rental: Rental) -> Rental:
    # Права могли истечь или быть лишены между бронью и стартом — проверяем допуск ещё раз.
    check_can_rent(rental.user, rental.car)
    _require_face_check(rental)
    _require_inspection(rental, "start")
    with transaction.atomic():
        rental = Rental.objects.select_for_update().select_related("car").get(pk=rental.pk)
        if rental.status != Rental.Status.RESERVED:
            raise ValidationError("Начать можно только забронированную поездку.")

        rental.started_at = timezone.now()
        rental.status = Rental.Status.ACTIVE
        rental.waiting_cost = calculate_waiting_cost(rental, rental.started_at)
        rental.save(update_fields=["status", "started_at", "waiting_cost"])

        rental.car.status = Car.Status.RENTED
        rental.car.save(update_fields=["status"])
    return rental


def finish_rental(rental: Rental, use_points=False) -> Rental:
    # Координаты от клиента не принимаются: иначе любой мог бы «переставить» машину
    # на карте у всех. Место парковки — текущая позиция машины.
    _require_inspection(rental, "finish")
    with transaction.atomic():
        rental = Rental.objects.select_for_update().select_related("car").get(pk=rental.pk)
        if rental.status != Rental.Status.ACTIVE:
            raise ValidationError("Завершить можно только активную поездку.")

        rental.finished_at = timezone.now()
        rental.status = Rental.Status.COMPLETED
        rental.end_latitude = rental.car.latitude
        rental.end_longitude = rental.car.longitude
        rental.total_cost = calculate_trip_cost(rental) + (rental.waiting_cost or Decimal("0"))
        if use_points:
            from rewards.services import spend_for_trip

            rental.points_spent, rental.points_discount = spend_for_trip(rental, rental.total_cost)
            rental.total_cost -= rental.points_discount
        rental.save(
            update_fields=[
                "status", "finished_at", "end_latitude", "end_longitude", "total_cost",
                "points_spent", "points_discount",
            ]
        )

        rental.car.status = Car.Status.AVAILABLE
        rental.car.save(update_fields=["status"])

    from rewards.services import on_trip_finished

    on_trip_finished(rental)
    return rental


@transaction.atomic
def cancel_rental(rental: Rental) -> Rental:
    rental = Rental.objects.select_for_update().select_related("car").get(pk=rental.pk)
    if rental.status != Rental.Status.RESERVED:
        raise ValidationError("Отменить можно только забронированную поездку.")

    rental.status = Rental.Status.CANCELLED
    rental.cancel_reason = Rental.CancelReason.USER
    rental.waiting_cost = calculate_waiting_cost(rental, timezone.now())
    rental.total_cost = rental.waiting_cost
    rental.save(update_fields=["status", "cancel_reason", "waiting_cost", "total_cost"])

    rental.car.status = Car.Status.AVAILABLE
    rental.car.save(update_fields=["status"])
    return rental


def report_car_missing(rental: Rental, origin, policy=None):
    """«Машины нет на месте»: бронь снимается без оплаты, машина уходит на проверку GPS."""
    if rental.status != Rental.Status.RESERVED:
        raise ValidationError("Сообщить можно только по активной брони.")
    car = rental.car
    if haversine_m(*origin, car.latitude, car.longitude) > settings.CAR_MISSING_RADIUS_M:
        raise ValidationError({"detail": "Вы ещё не дошли до машины.", "code": "too_far"})
    day_ago = timezone.now() - timedelta(hours=24)
    recent = Rental.objects.filter(
        user=rental.user, cancel_reason=Rental.CancelReason.CAR_MISSING, reserved_at__gte=day_ago
    ).count()
    if recent >= settings.CAR_MISSING_DAILY_LIMIT:
        raise ValidationError({"detail": "Лимит на сутки исчерпан — напишите в поддержку.", "code": "limit"})

    with transaction.atomic():
        rental = Rental.objects.select_for_update().select_related("car").get(pk=rental.pk)
        if rental.status != Rental.Status.RESERVED:
            raise ValidationError("Сообщить можно только по активной брони.")
        rental.status = Rental.Status.CANCELLED
        rental.cancel_reason = Rental.CancelReason.CAR_MISSING
        rental.waiting_cost = Decimal("0.00")
        rental.total_cost = Decimal("0.00")
        rental.save(update_fields=["status", "cancel_reason", "waiting_cost", "total_cost"])
        rental.car.status = Car.Status.MAINTENANCE
        rental.car.save(update_fields=["status"])
    return rental, nearest_alternative(rental.user, origin, exclude=rental.car_id, policy=policy)


def nearest_alternative(user, origin, exclude=None, policy=None):
    """Ближайшая свободная машина, которую этому водителю можно брать.

    Бесплатные минуты считает CarSerializer по тому же правилу, что и бронь
    (нужны origin и access_policy в контексте).
    """
    policy = policy or access_policy(user)
    allowed = [cls for cls, entry in policy["classes"].items() if entry["allowed"]]
    candidates = list(
        Car.objects.filter(status=Car.Status.AVAILABLE, car_class__in=allowed)
        .exclude(pk=exclude)
        .select_related("tariff")
        .prefetch_related("features")
    )
    if not candidates:
        return None
    walks = walking_matrix(origin, [(car.latitude, car.longitude) for car in candidates])
    car, walk = min(zip(candidates, walks), key=lambda pair: pair[1]["duration_s"])
    car.walk = walk
    return car

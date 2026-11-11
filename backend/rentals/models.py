import math
from datetime import timedelta

from django.conf import settings
from django.db import models


class Rental(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Забронирована"
        ACTIVE = "active", "В поездке"
        COMPLETED = "completed", "Завершена"
        CANCELLED = "cancelled", "Отменена"

    class CancelReason(models.TextChoices):
        NONE = "", "—"
        USER = "user", "Отменил клиент"
        CAR_MISSING = "car_missing", "Машины не было на месте"

    ACTIVE_STATUSES = (Status.RESERVED, Status.ACTIVE)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="rentals",
    )
    car = models.ForeignKey(
        "cars.Car", verbose_name="Автомобиль", on_delete=models.PROTECT, related_name="rentals"
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.RESERVED
    )
    reserved_at = models.DateTimeField("Забронирована", auto_now_add=True)
    started_at = models.DateTimeField("Начало поездки", null=True, blank=True)
    finished_at = models.DateTimeField("Конец поездки", null=True, blank=True)
    # Цены фиксируются в момент брони: изменение тарифа не меняет стоимость прошлых поездок.
    price_per_minute_at_booking = models.DecimalField(
        "Поездка на момент брони, BYN/мин", max_digits=6, decimal_places=2
    )
    waiting_price_per_minute_at_booking = models.DecimalField(
        "Ожидание на момент брони, BYN/мин", max_digits=6, decimal_places=2, default=0
    )
    price_per_hour_at_booking = models.DecimalField(
        "Пакет «час» на момент брони, BYN", max_digits=8, decimal_places=2, null=True, blank=True
    )
    price_per_day_at_booking = models.DecimalField(
        "Пакет «сутки» на момент брони, BYN",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    start_latitude = models.FloatField("Широта старта", null=True, blank=True)
    start_longitude = models.FloatField("Долгота старта", null=True, blank=True)
    end_latitude = models.FloatField("Широта финиша", null=True, blank=True)
    end_longitude = models.FloatField("Долгота финиша", null=True, blank=True)
    # «Честная бронь»: окно бесплатного ожидания считается по пешему пути клиента.
    free_waiting_minutes = models.PositiveSmallIntegerField("Бесплатное ожидание, мин", default=10)
    walk_duration_s = models.PositiveIntegerField("Пешком до машины, с", null=True, blank=True)
    walk_distance_m = models.PositiveIntegerField("Пешком до машины, м", null=True, blank=True)
    walk_source = models.CharField("Источник маршрута", max_length=10, blank=True)
    client_latitude = models.FloatField("Широта клиента при брони", null=True, blank=True)
    client_longitude = models.FloatField("Долгота клиента при брони", null=True, blank=True)
    cancel_reason = models.CharField(
        "Причина отмены", max_length=20, choices=CancelReason.choices, blank=True, default=""
    )
    # «Лицо водителя»: перед стартом владелец аккаунта проходит короткую проверку перед камерой.
    driver_check = models.ForeignKey(
        "accounts.LivenessCheck",
        verbose_name="Проверка лица перед поездкой",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rentals",
    )
    compensation_minutes = models.PositiveSmallIntegerField(
        "Бесплатные минуты по гарантии Signature", default=0
    )
    # «Движ»: часть поездки можно оплатить баллами (до 30%), скидка уже вычтена из итога.
    points_spent = models.PositiveIntegerField("Списано баллов", default=0)
    points_discount = models.DecimalField("Скидка баллами, BYN", max_digits=8, decimal_places=2, default=0)
    waiting_cost = models.DecimalField(
        "Платное ожидание, BYN", max_digits=10, decimal_places=2, null=True, blank=True
    )
    total_cost = models.DecimalField(
        "Итого, BYN", max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "Аренда"
        verbose_name_plural = "Аренды"
        ordering = ("-reserved_at",)

    def __str__(self):
        return f"Аренда #{self.pk} — {self.car} — {self.get_status_display()}"

    @property
    def duration_minutes(self):
        """Тарифицируемые минуты поездки: округление вверх, минимум одна."""
        if not self.started_at or not self.finished_at:
            return None
        return max(1, math.ceil((self.finished_at - self.started_at).total_seconds() / 60))

    @property
    def trip_cost(self):
        if self.total_cost is None or self.status != self.Status.COMPLETED:
            return None
        # Цена самой поездки до скидки баллами: скидка показывается в чеке отдельной строкой.
        return self.total_cost - (self.waiting_cost or 0) + (self.points_discount or 0)

    @property
    def free_waiting_until(self):
        if not self.reserved_at:
            return None
        return self.reserved_at + timedelta(minutes=self.free_waiting_minutes)

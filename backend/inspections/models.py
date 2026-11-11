from django.conf import settings
from django.db import models
from django.utils import timezone

GENESIS_HASH = "0" * 64


class Inspection(models.Model):
    """Акт осмотра машины. Каждый акт запечатан хэшем, включающим хэш предыдущего."""

    class Kind(models.TextChoices):
        START = "start", "До поездки"
        FINISH = "finish", "После поездки"

    class Cleanliness(models.IntegerChoices):
        CLEAN = 1, "Чисто"
        LITTER = 2, "Есть мусор"
        DIRTY = 3, "Грязно"

    rental = models.ForeignKey(
        "rentals.Rental", verbose_name="Аренда", on_delete=models.PROTECT, related_name="inspections"
    )
    car = models.ForeignKey(
        "cars.Car", verbose_name="Автомобиль", on_delete=models.PROTECT, related_name="inspections"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Клиент", on_delete=models.PROTECT, related_name="inspections"
    )
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices)
    # Время ставится явно и входит в хэш, поэтому не auto_now_add.
    created_at = models.DateTimeField("Время акта", default=timezone.now)
    latitude = models.FloatField("Широта", null=True, blank=True)
    longitude = models.FloatField("Долгота", null=True, blank=True)
    cleanliness = models.PositiveSmallIntegerField(
        "Чистота", choices=Cleanliness.choices, null=True, blank=True
    )
    confirmed_as_passport = models.BooleanField("«Всё как в паспорте»", default=False)
    prev_hash = models.CharField("Хэш предыдущего акта", max_length=64)
    seal_hash = models.CharField("Печать (SHA-256)", max_length=64, unique=True)

    class Meta:
        verbose_name = "Акт осмотра"
        verbose_name_plural = "Акты осмотра"
        ordering = ("created_at", "id")
        constraints = [models.UniqueConstraint(fields=["rental", "kind"], name="one_act_per_rental_kind")]

    def __str__(self):
        return f"Акт #{self.seal_short} — {self.car} — {self.get_kind_display()}"

    @property
    def seal_short(self):
        return self.seal_hash[:6]


class InspectionPhoto(models.Model):
    class Angle(models.TextChoices):
        FRONT = "front", "Спереди"
        REAR = "rear", "Сзади"
        LEFT = "left", "Слева"
        RIGHT = "right", "Справа"
        INTERIOR = "interior", "Салон"

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="photos")
    angle = models.CharField("Ракурс", max_length=10, choices=Angle.choices)
    # Фото машины — не персональные данные, поэтому обычное публичное хранилище.
    image = models.ImageField("Фото", upload_to="inspections/%Y/%m/")
    sha256 = models.CharField("SHA-256 файла", max_length=64)
    brightness = models.FloatField("Яркость", default=0)
    sharpness = models.FloatField("Резкость", default=0)

    class Meta:
        verbose_name = "Фото осмотра"
        verbose_name_plural = "Фото осмотра"
        constraints = [models.UniqueConstraint(fields=["inspection", "angle"], name="one_photo_per_angle")]


class Damage(models.Model):
    """Отметка повреждения на силуэте машины (координаты — доли ширины и длины)."""

    class Severity(models.TextChoices):
        SCRATCH = "scratch", "Царапина"
        DENT = "dent", "Вмятина"
        CRACK = "crack", "Скол или трещина"

    class Status(models.TextChoices):
        KNOWN = "known", "Известно"
        NEW = "new", "Новое"
        DISPUTED = "disputed", "Претензия отклонена"
        CONFIRMED = "confirmed", "Вина подтверждена"
        REPAIRED = "repaired", "Устранено"

    ACTIVE = (Status.KNOWN, Status.NEW, Status.DISPUTED, Status.CONFIRMED)

    car = models.ForeignKey("cars.Car", verbose_name="Автомобиль", on_delete=models.CASCADE, related_name="damages")
    x = models.FloatField("X (0–1)")
    y = models.FloatField("Y (0–1)")
    severity = models.CharField("Тип", max_length=10, choices=Severity.choices)
    photo = models.ForeignKey(
        InspectionPhoto, verbose_name="Фото", on_delete=models.SET_NULL, null=True, blank=True
    )
    first_seen = models.ForeignKey(
        Inspection,
        verbose_name="Впервые в акте",
        on_delete=models.PROTECT,
        related_name="first_damages",
    )
    responsible_rental = models.ForeignKey(
        "rentals.Rental",
        verbose_name="Ответственная поездка",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blamed_damages",
    )
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW)
    claim_note = models.TextField("Решение по претензии", blank=True)
    created_at = models.DateTimeField("Отмечено", auto_now_add=True)
    repaired_at = models.DateTimeField("Устранено", null=True, blank=True)

    class Meta:
        verbose_name = "Повреждение"
        verbose_name_plural = "Повреждения"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_severity_display()} — {self.car} ({self.get_status_display()})"

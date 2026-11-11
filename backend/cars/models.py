from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Tariff(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    price_per_minute = models.DecimalField("Поездка, BYN/мин", max_digits=6, decimal_places=2)
    waiting_price_per_minute = models.DecimalField(
        "Ожидание, BYN/мин", max_digits=6, decimal_places=2, default=0
    )
    price_per_hour = models.DecimalField(
        "Пакет «час», BYN", max_digits=8, decimal_places=2, null=True, blank=True
    )
    price_per_day = models.DecimalField(
        "Пакет «сутки», BYN", max_digits=8, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "Тариф"
        verbose_name_plural = "Тарифы"
        ordering = ("price_per_minute",)

    def __str__(self):
        return f"{self.name} ({self.price_per_minute} BYN/мин)"


class Feature(models.Model):
    """Опция автомобиля: камера, подогрев сидений и т. п."""

    name = models.CharField("Название", max_length=80, unique=True)

    class Meta:
        verbose_name = "Опция"
        verbose_name_plural = "Опции"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Car(models.Model):
    class CarClass(models.TextChoices):
        ECONOMY = "economy", "Эконом"
        COMFORT = "comfort", "Комфорт"
        BUSINESS = "business", "Бизнес"
        PREMIUM = "premium", "Премиум"

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Механика"
        AUTOMATIC = "automatic", "Автомат"

    class FuelType(models.TextChoices):
        PETROL = "petrol", "Бензин"
        DIESEL = "diesel", "Дизель"
        HYBRID = "hybrid", "Гибрид"
        ELECTRIC = "electric", "Электро"

    class Livery(models.TextChoices):
        NONE = "none", "Без оклейки"
        GRAPHITE = "graphite", "Signature · графит"
        IVORY = "ivory", "Signature · слоновая кость"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Свободен"
        RESERVED = "reserved", "Забронирован"
        RENTED = "rented", "В аренде"
        MAINTENANCE = "maintenance", "На обслуживании"

    brand = models.CharField("Марка", max_length=50)
    model = models.CharField("Модель", max_length=50)
    year = models.PositiveIntegerField(
        "Год выпуска", validators=[MinValueValidator(1990), MaxValueValidator(2100)]
    )
    license_plate = models.CharField("Госномер", max_length=15, unique=True)
    car_class = models.CharField(
        "Класс", max_length=20, choices=CarClass.choices, default=CarClass.ECONOMY
    )
    transmission = models.CharField(
        "Коробка передач",
        max_length=20,
        choices=Transmission.choices,
        default=Transmission.AUTOMATIC,
    )
    fuel_type = models.CharField(
        "Тип топлива", max_length=20, choices=FuelType.choices, default=FuelType.PETROL
    )
    engine_volume = models.DecimalField(
        "Объём двигателя, л", max_digits=3, decimal_places=1, null=True, blank=True
    )
    horsepower = models.PositiveSmallIntegerField("Мощность, л. с.", null=True, blank=True)
    color = models.CharField("Цвет", max_length=30, blank=True)
    livery = models.CharField(
        "Фирменная оклейка",
        max_length=10,
        choices=Livery.choices,
        default=Livery.NONE,
        help_text="Машины в оклейке «Рули Signature» идут с гарантией чистоты",
    )
    seats = models.PositiveSmallIntegerField("Количество мест", default=5)
    features = models.ManyToManyField(
        Feature, verbose_name="Опции", related_name="cars", blank=True
    )
    tariff = models.ForeignKey(
        Tariff, verbose_name="Тариф", on_delete=models.PROTECT, related_name="cars"
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.AVAILABLE
    )
    latitude = models.FloatField(
        "Широта", validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.FloatField(
        "Долгота", validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    address = models.CharField("Адрес парковки", max_length=200, blank=True)
    photo = models.ImageField("Фотография", upload_to="cars/", null=True, blank=True)
    photo_url = models.CharField(
        "Путь к фото", max_length=300, blank=True, help_text="Используется, если файл не загружен"
    )
    odometer_km = models.PositiveIntegerField("Пробег, км", default=0)
    fuel_level_percent = models.PositiveSmallIntegerField(
        "Уровень топлива, %", default=100, validators=[MaxValueValidator(100)]
    )
    last_cleaned_at = models.DateTimeField("Последняя мойка", null=True, blank=True)
    needs_cleaning = models.BooleanField("Нужна мойка", default=False)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ("brand", "model")

    def __str__(self):
        return f"{self.brand} {self.model} ({self.license_plate})"

    @property
    def title(self):
        return f"{self.brand} {self.model}"

    @property
    def is_signature(self):
        return self.livery != self.Livery.NONE

    @property
    def image_url(self):
        return self.photo.url if self.photo else self.photo_url

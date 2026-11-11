from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Car, Feature, Tariff


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_per_minute",
        "waiting_price_per_minute",
        "price_per_hour",
        "price_per_day",
        "cars_count",
    )
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_cars_count=Count("cars"))

    @admin.display(description="Автомобилей", ordering="_cars_count")
    def cars_count(self, obj):
        return obj._cars_count


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ("name", "cars_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_cars_count=Count("cars"))

    @admin.display(description="Автомобилей", ordering="_cars_count")
    def cars_count(self, obj):
        return obj._cars_count


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail",
        "license_plate",
        "brand",
        "model",
        "year",
        "car_class",
        "status",
        "tariff",
        "fuel_level_percent",
        "address",
    )
    list_display_links = ("thumbnail", "license_plate")
    list_filter = ("status", "car_class", "transmission", "fuel_type", "tariff")
    search_fields = ("brand", "model", "license_plate", "address")
    list_editable = ("status",)
    filter_horizontal = ("features",)
    readonly_fields = ("preview", "created_at")
    actions = ("make_available", "send_to_maintenance")
    fieldsets = (
        (
            "Автомобиль",
            {
                "fields": (
                    ("brand", "model", "year"),
                    ("license_plate", "color", "seats"),
                    ("photo", "photo_url"),
                    "preview",
                )
            },
        ),
        (
            "Характеристики",
            {
                "fields": (
                    ("car_class", "tariff"),
                    ("transmission", "fuel_type"),
                    ("engine_volume", "horsepower"),
                    "features",
                )
            },
        ),
        (
            "Состояние и парковка",
            {
                "fields": (
                    "status",
                    "address",
                    ("latitude", "longitude"),
                    ("odometer_km", "fuel_level_percent"),
                    "created_at",
                )
            },
        ),
    )

    @admin.display(description="Фото")
    def thumbnail(self, obj):
        if not obj.image_url:
            return "—"
        return format_html(
            '<img src="{}" style="width:72px;height:46px;object-fit:cover;border-radius:8px">',
            obj.image_url,
        )

    @admin.display(description="Превью")
    def preview(self, obj):
        if not obj.image_url:
            return "Фото не загружено"
        return format_html(
            '<img src="{}" style="max-width:360px;border-radius:12px">', obj.image_url
        )

    @admin.action(description="Сделать свободными")
    def make_available(self, request, queryset):
        updated = queryset.exclude(status__in=(Car.Status.RESERVED, Car.Status.RENTED)).update(
            status=Car.Status.AVAILABLE
        )
        self.message_user(request, f"Свободными отмечено автомобилей: {updated}.")

    @admin.action(description="Отправить на обслуживание")
    def send_to_maintenance(self, request, queryset):
        updated = queryset.exclude(status__in=(Car.Status.RESERVED, Car.Status.RENTED)).update(
            status=Car.Status.MAINTENANCE
        )
        self.message_user(
            request,
            f"На обслуживание отправлено: {updated}. Машины в аренде и брони не затронуты.",
        )

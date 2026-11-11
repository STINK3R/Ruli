from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from rest_framework.exceptions import APIException

from cars.models import Car

from .chain import verify_chain
from .models import Damage, Inspection, InspectionPhoto
from .services import open_claim


class PhotoInline(admin.TabularInline):
    model = InspectionPhoto
    extra = 0
    can_delete = False
    fields = ("preview", "angle", "sha256", "brightness", "sharpness")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Фото")
    def preview(self, obj):
        return format_html(
            '<a href="{0}" target="_blank"><img src="{0}" style="height:70px;border-radius:8px"></a>',
            obj.image.url,
        )


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    """Акты только для чтения: их правка сломала бы цепочку хэшей."""

    list_display = ("seal_short", "car", "kind", "user", "rental", "created_at", "cleanliness")
    list_filter = ("kind", "car")
    inlines = (PhotoInline,)
    actions = ("check_chain",)
    readonly_fields = (
        "rental", "car", "user", "kind", "created_at", "latitude", "longitude",
        "cleanliness", "confirmed_as_passport", "prev_hash", "seal_hash",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Печать")
    def seal_short(self, obj):
        return f"#{obj.seal_short}"

    @admin.action(description="Проверить целостность цепочки машин")
    def check_chain(self, request, queryset):
        for car in Car.objects.filter(inspections__in=queryset).distinct():
            result = verify_chain(car)
            if result["ok"]:
                self.message_user(request, f"{car}: цепочка цела, актов {result['checked']}.", messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    f"{car}: цепочка нарушена на акте #{result['broken_seal']} — {result['reason_text']}.",
                    messages.ERROR,
                )


@admin.register(Damage)
class DamageAdmin(admin.ModelAdmin):
    list_display = ("car", "severity", "status", "position", "first_seen", "responsible_rental", "created_at")
    list_filter = ("status", "severity", "car")
    readonly_fields = ("first_seen", "photo_preview", "created_at")
    actions = ("claim", "send_to_repair", "mark_repaired")

    @admin.display(description="Точка")
    def position(self, obj):
        return f"{obj.x:.2f} × {obj.y:.2f}"

    @admin.display(description="Фото")
    def photo_preview(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="max-width:320px;border-radius:10px">', obj.photo.image.url)

    @admin.action(description="Претензия к ответственной поездке (окно 24 ч)")
    def claim(self, request, queryset):
        for damage in queryset.select_related("responsible_rental", "first_seen"):
            try:
                damage = open_claim(damage)
                level = messages.SUCCESS if damage.status == Damage.Status.CONFIRMED else messages.WARNING
                self.message_user(request, f"{damage}: {damage.claim_note}", level)
            except APIException as error:
                self.message_user(request, f"{damage}: {error.detail}", messages.ERROR)

    @admin.action(description="Отправить машину в ремонт")
    def send_to_repair(self, request, queryset):
        cars = Car.objects.filter(damages__in=queryset).exclude(
            status__in=(Car.Status.RESERVED, Car.Status.RENTED)
        )
        updated = cars.update(status=Car.Status.MAINTENANCE)
        self.message_user(request, f"На обслуживание отправлено машин: {updated}.")

    @admin.action(description="Повреждение устранено")
    def mark_repaired(self, request, queryset):
        updated = queryset.update(status=Damage.Status.REPAIRED, repaired_at=timezone.now())
        self.message_user(request, f"Отмечено устранённым: {updated}.")

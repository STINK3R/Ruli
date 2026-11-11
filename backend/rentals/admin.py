from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import Rental


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "car",
        "status",
        "reserved_at",
        "started_at",
        "finished_at",
        "duration",
        "waiting_cost",
        "total_cost",
    )
    list_filter = ("status", "reserved_at")
    search_fields = ("user__username", "car__license_plate", "car__brand", "car__model")
    autocomplete_fields = ("user", "car")
    readonly_fields = (
        "reserved_at",
        "price_per_minute_at_booking",
        "waiting_price_per_minute_at_booking",
        "price_per_hour_at_booking",
        "price_per_day_at_booking",
        "waiting_cost",
        "total_cost",
        "driver_face",
    )
    date_hierarchy = "reserved_at"
    list_select_related = ("user", "car")

    @admin.display(description="Длительность, мин")
    def duration(self, obj):
        return obj.duration_minutes

    @admin.display(description="Лицо водителя перед стартом")
    def driver_face(self, obj):
        check = obj.driver_check
        if check is None:
            return "Проверка не проходилась"
        frames = format_html_join(
            "",
            '<a href="{0}" target="_blank"><img src="{0}" style="height:110px;margin-right:8px;border-radius:8px"></a>',
            ((reverse("admin:accounts_livenessframe_file", args=[frame.pk]),) for frame in check.frames.all()),
        )
        return format_html(
            "{}<div style='font-size:12px;color:#777'>{} · движение {}{}</div>",
            frames,
            check.get_status_display(),
            check.motion_score,
            " · демо" if check.is_demo else "",
        )

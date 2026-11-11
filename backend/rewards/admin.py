from django.contrib import admin

from .models import PointsEntry, Referral


@admin.register(PointsEntry)
class PointsEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "amount", "kind", "title")
    list_filter = ("kind",)
    search_fields = ("user__username", "user__last_name", "title")
    autocomplete_fields = ("user",)
    raw_id_fields = ("rental",)
    readonly_fields = ("created_at",)

    # Журнал не переписывается: исправление — новой строкой «Бонус от Рули» с нужным знаком.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referee", "created_at", "rewarded_at")
    readonly_fields = ("referrer", "referee", "created_at", "rewarded_at")

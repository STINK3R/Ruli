from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from rest_framework.exceptions import APIException

from django.conf import settings

from . import kyc
from . import verification as service
from .models import (
    ClassRequirement,
    DriverVerification,
    LicenseRegistryRecord,
    LivenessCheck,
    LivenessFrame,
    User,
    VerificationDocument,
    VerificationEvent,
)

LEVEL_ICONS = {"fail": "⛔", "warn": "⚠️", "ok": "✅"}


class AuditCascadeMixin:
    """Журнал Рули ID по одной записи не удалить, но он уходит вместе с заявкой или пользователем.

    Без этого запрет удаления событий заблокировал бы и удаление владельца.
    """

    def get_deleted_objects(self, objs, request):
        deleted, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        perms_needed.discard(VerificationEvent._meta.verbose_name)
        return deleted, model_count, perms_needed, protected


@admin.register(User)
class UserAdmin(AuditCascadeMixin, BaseUserAdmin):
    list_display = (
        "username",
        "full_name",
        "email",
        "phone_number",
        "verification_status",
        "is_staff",
        "date_joined",
    )
    list_filter = ("verification_status", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")
    readonly_fields = ("license_key", "phone_verified_at")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Рули ID",
            {
                "description": "Данные водителя копируются из одобренной заявки.",
                "fields": (
                    "patronymic",
                    "phone_number",
                    "phone_verified_at",
                    "verification_status",
                    "date_of_birth",
                    "driver_license_number",
                    "driver_license_issued",
                    "driving_since",
                    "license_expires_on",
                    "license_key",
                ),
            },
        ),
    )


@admin.register(ClassRequirement)
class ClassRequirementAdmin(admin.ModelAdmin):
    list_display = ("car_class", "min_age", "min_experience_years", "min_completed_rentals", "note")
    list_editable = ("min_age", "min_experience_years", "min_completed_rentals", "note")


class EventInline(admin.TabularInline):
    model = VerificationEvent
    extra = 0
    can_delete = False
    fields = ("created_at", "action", "actor", "meta")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _decide(modeladmin, request, queryset, decision, success, **kwargs):
    done = 0
    for verification in queryset:
        try:
            decision(verification, request.user, **kwargs)
            done += 1
        except APIException as error:
            modeladmin.message_user(request, f"Заявка #{verification.pk}: {error.detail}", messages.ERROR)
    if done:
        modeladmin.message_user(request, f"{success}: {done}.", messages.SUCCESS)


@admin.register(DriverVerification)
class DriverVerificationAdmin(AuditCascadeMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "submitted_at",
        "waiting",
        "risk",
        "warnings_count",
        "rejection_reason",
        "source",
    )
    list_filter = ("status", "source", "rejection_reason")
    search_fields = ("user__username", "user__last_name", "full_name_on_document")
    ordering = ("submitted_at", "id")
    inlines = (EventInline,)
    readonly_fields = (
        "user",
        "status",
        "source",
        "documents_preview",
        "liveness_preview",
        "checks",
        "risk",
        "registry",
        "liveness_passed_at",
        "license_number_normalized",
        "consent_version",
        "consent_given_at",
        "biometric_consent_at",
        "submitted_at",
        "reviewed_at",
        "reviewer",
        "files_purged_at",
        "created_at",
    )
    fieldsets = (
        ("Заявка", {"fields": ("user", "status", "source", "submitted_at", "reviewed_at", "reviewer")}),
        ("Документы и лицо", {"fields": ("documents_preview", "liveness_preview", "liveness_passed_at")}),
        ("Автопроверки", {"fields": ("risk", "checks", "registry")}),
        (
            "Данные из документов",
            {
                "fields": (
                    "document_type",
                    "full_name_on_document",
                    "date_of_birth",
                    "personal_number",
                    "license_country",
                    "license_number",
                    "license_number_normalized",
                    ("license_issued_on", "license_expires_on"),
                    ("category_b_since", "experience_since_override"),
                )
            },
        ),
        ("Решение", {"fields": ("rejection_reason", "reviewer_comment", "internal_note")}),
        (
            "Согласия (Закон РБ № 99-З)",
            {"fields": ("consent_version", "consent_given_at", "biometric_consent_at", "files_purged_at")},
        ),
    )
    actions = (
        "approve_selected",
        "fix_blurry",
        "fix_glare",
        "reject_data_mismatch",
        "reject_expired",
        "revoke_selected",
    )

    def get_urls(self):
        return [
            path(
                "<int:pk>/document/<str:kind>/",
                self.admin_site.admin_view(self.document_view),
                name="accounts_driververification_document",
            ),
            path(
                "frame/<int:frame_id>/",
                self.admin_site.admin_view(self.frame_view),
                name="accounts_livenessframe_file",
            ),
            *super().get_urls(),
        ]

    def document_view(self, request, pk, kind):
        """Отдаёт фото документа только сотрудникам и пишет просмотр в журнал."""
        if not self.has_view_permission(request):
            raise Http404
        document = get_object_or_404(VerificationDocument, verification_id=pk, kind=kind)
        service.log(document.verification, VerificationEvent.Action.DOCUMENT_VIEWED, request.user, kind=kind)
        response = FileResponse(document.file.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "no-store"
        return response

    def frame_view(self, request, frame_id):
        """Кадр проверки «живости» — только сотрудникам, каждый просмотр в журнале."""
        if not self.has_view_permission(request):
            raise Http404
        frame = get_object_or_404(LivenessFrame.objects.select_related("check_run"), pk=frame_id)
        verification = frame.check_run.verification or frame.check_run.user.verifications.first()
        if verification:
            service.log(verification, VerificationEvent.Action.DOCUMENT_VIEWED, request.user,
                        kind=f"liveness:{frame.step}")
        response = FileResponse(frame.file.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "no-store"
        return response

    def changelist_view(self, request, extra_context=None):
        in_queue = DriverVerification.objects.filter(status=DriverVerification.Status.PENDING).count()
        extra_context = {
            **(extra_context or {}),
            "title": f"Очередь Рули ID — на проверке {in_queue}, "
            f"медиана решения {service.expected_wait_minutes()} мин",
        }
        return super().changelist_view(request, extra_context)

    @admin.display(description="Ждёт")
    def waiting(self, obj):
        if obj.status != DriverVerification.Status.PENDING or not obj.submitted_at:
            return "—"
        minutes = int((timezone.now() - obj.submitted_at).total_seconds() // 60)
        return f"{minutes} мин"

    @admin.display(description="Фото документов")
    def documents_preview(self, obj):
        documents = list(obj.documents.all())
        if not documents:
            return "Файлов нет" + (" (удалены по сроку хранения)" if obj.files_purged_at else "")
        return format_html_join(
            "",
            '<figure style="display:inline-block;margin:0 12px 12px 0;text-align:center">'
            '<a href="{0}" target="_blank"><img src="{0}" style="width:220px;height:150px;'
            'object-fit:cover;border-radius:10px;border:{2}"></a>'
            '<figcaption style="font-size:12px">{1}</figcaption></figure>',
            (
                (
                    reverse("admin:accounts_driververification_document", args=[obj.pk, doc.kind]),
                    doc.get_kind_display()
                    + (" — переснять" if doc.needs_reshoot else "")
                    + (" · ДЕМО" if doc.is_demo else ""),
                    "3px solid #A3392B" if doc.needs_reshoot else ("3px dashed #C9AC74" if doc.is_demo else "1px solid #DDD5C7"),
                )
                for doc in documents
            ),
        )

    @admin.display(description="Проверка «живости»")
    def liveness_preview(self, obj):
        check = obj.liveness_checks.filter(status=LivenessCheck.Status.PASSED).first()
        if check is None:
            failed = obj.liveness_checks.filter(status=LivenessCheck.Status.FAILED).count()
            return f"Не пройдена (неудачных попыток: {failed})" if failed else "Не пройдена"
        labels = dict(kyc.STEP_LABELS)
        frames = format_html_join(
            "",
            '<figure style="display:inline-block;margin:0 10px 10px 0;text-align:center">'
            '<a href="{0}" target="_blank"><img src="{0}" style="width:150px;height:150px;'
            'object-fit:cover;border-radius:10px;border:1px solid #DDD5C7"></a>'
            '<figcaption style="font-size:11px;max-width:150px">{1}</figcaption></figure>',
            (
                (reverse("admin:accounts_livenessframe_file", args=[frame.pk]), labels.get(frame.step, frame.step))
                for frame in check.frames.all()
            ),
        )
        note = format_html(
            "<div style='font-size:12px;color:#777'>Движение в кадре: {} (порог {}){}. "
            "Сравните лицо с фото в паспорте и на селфи с правами.</div>",
            check.motion_score,
            settings.LIVENESS_MIN_MOTION,
            " · ДЕМО-КАДРЫ" if check.is_demo else "",
        )
        return format_html("{}{}", frames, note)

    @admin.display(description="Риск", ordering="risk_score")
    def risk(self, obj):
        color = "#A3392B" if obj.risk_score >= 50 else ("#946414" if obj.risk_score >= 20 else "#3F5E3A")
        return format_html('<b style="color:{}">{}</b>', color, obj.risk_score)

    @admin.display(description="Реестр ГАИ (имитация)")
    def registry(self, obj):
        record = kyc.registry_lookup(obj.license_number_normalized or service.normalize_license(obj.license_number))
        if record is None:
            return "Запись не найдена"
        return format_html(
            "{} · {} · рожд. {:%d.%m.%Y} · выдано {:%d.%m.%Y} · до {:%d.%m.%Y} · кат. {}",
            record.get_status_display(),
            record.full_name,
            record.date_of_birth,
            record.issued_on,
            record.expires_on,
            record.categories,
        )

    @admin.display(description="Автопроверки")
    def checks(self, obj):
        if not obj.auto_checks:
            return "Ещё не запускались"
        return format_html(
            "<ul style='margin:0;padding-left:18px'>{}</ul>",
            format_html_join(
                "",
                "<li>{} {}</li>",
                ((LEVEL_ICONS.get(c["level"], "•"), c["message"]) for c in obj.auto_checks),
            ),
        )

    @admin.action(description="Одобрить")
    def approve_selected(self, request, queryset):
        _decide(self, request, queryset, service.approve, "Одобрено")

    @admin.action(description="Переснять: фото размыто")
    def fix_blurry(self, request, queryset):
        _decide(self, request, queryset, service.request_fix, "Отправлено на пересъёмку", reason="blurry_photo")

    @admin.action(description="Переснять: блик на документе")
    def fix_glare(self, request, queryset):
        _decide(self, request, queryset, service.request_fix, "Отправлено на пересъёмку", reason="glare")

    @admin.action(description="Отклонить: данные не совпадают")
    def reject_data_mismatch(self, request, queryset):
        _decide(self, request, queryset, service.reject, "Отклонено", reason="data_mismatch")

    @admin.action(description="Отклонить: ВУ просрочено")
    def reject_expired(self, request, queryset):
        _decide(self, request, queryset, service.reject, "Отклонено", reason="license_expired")

    @admin.action(description="Отозвать одобрение")
    def revoke_selected(self, request, queryset):
        _decide(self, request, queryset, service.revoke, "Одобрение отозвано", reason="other")


@admin.register(VerificationEvent)
class VerificationEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "verification", "action", "actor")
    list_filter = ("action",)
    readonly_fields = ("verification", "actor", "action", "meta", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Журнал аудита (в том числе просмотров фото сотрудниками) стирать нельзя.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LicenseRegistryRecord)
class LicenseRegistryAdmin(admin.ModelAdmin):
    list_display = ("number_normalized", "full_name", "date_of_birth", "expires_on", "categories", "status", "note")
    list_filter = ("status",)
    search_fields = ("number_normalized", "full_name")


class LivenessFrameInline(admin.TabularInline):
    model = LivenessFrame
    extra = 0
    can_delete = False
    fields = ("step", "preview", "uploaded_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Кадр")
    def preview(self, obj):
        url = reverse("admin:accounts_livenessframe_file", args=[obj.pk])
        return format_html('<a href="{0}" target="_blank"><img src="{0}" style="height:90px;border-radius:8px"></a>', url)


@admin.register(LivenessCheck)
class LivenessCheckAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "purpose", "status", "motion_score", "is_demo", "created_at")
    list_filter = ("purpose", "status", "is_demo")
    search_fields = ("user__username", "user__last_name")
    readonly_fields = (
        "user", "verification", "purpose", "steps", "status", "motion_score",
        "failure_reason", "is_demo", "created_at", "expires_at", "completed_at",
    )
    inlines = (LivenessFrameInline,)

    def has_add_permission(self, request):
        return False

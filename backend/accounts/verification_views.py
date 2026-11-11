from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import kyc
from . import verification as service
from .images import process_document_image
from .models import (
    ClassRequirement,
    DriverVerification,
    LivenessCheck,
    LivenessFrame,
    VerificationDocument,
    VerificationEvent,
)
from .serializers import ClassRequirementSerializer, DriverVerificationSerializer

V = DriverVerification.Status
EDITABLE = (V.DRAFT, V.NEEDS_FIX)
SELFIE = VerificationDocument.Kind.SELFIE


def latest_verification(user):
    return user.verifications.exclude(status=V.SUPERSEDED).order_by("-created_at", "-id").first()


def open_verification(user):
    verification = user.verifications.filter(status__in=EDITABLE).order_by("-created_at").first()
    if verification is None:
        raise ValidationError({"detail": "Нет заявки, которую можно изменить.", "code": "no_open_request"})
    return verification


def verification_payload(user):
    # Сервисы меняют статус через свой экземпляр пользователя — перечитываем.
    user.refresh_from_db()
    verification = latest_verification(user)
    return {
        "verification": DriverVerificationSerializer(verification).data if verification else None,
        "access": service.access_policy(user),
        "expected_wait_minutes": service.expected_wait_minutes(),
        "consent_version": settings.CONSENT_VERSION,
        "phone": {"number": user.phone_number, "verified": user.phone_verified},
        "demo_mode": settings.KYC_DEMO_MODE,
    }


def is_demo_request(request):
    demo = str(request.data.get("demo", "")).lower() in ("1", "true", "yes")
    if demo and not settings.KYC_DEMO_MODE:
        raise ValidationError({"detail": "Демо-изображения отключены — снимите настоящий документ.", "code": "demo_disabled"})
    return demo


def liveness_payload(check):
    return {
        "id": check.id,
        "purpose": check.purpose,
        "status": check.status,
        "steps": kyc.describe_steps(check.steps),
        "expires_at": check.expires_at,
        "ttl_seconds": settings.LIVENESS_TTL_SECONDS,
    }


class RequirementsView(generics.ListAPIView):
    """Требования по классам — видны всем, даже до регистрации."""

    queryset = ClassRequirement.objects.all()
    serializer_class = ClassRequirementSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class VerificationView(APIView):
    def get(self, request):
        return Response(verification_payload(request.user))

    def post(self, request):
        """Открыть черновик заявки (или вернуть уже открытый)."""
        user = request.user
        service.ensure_not_blocked(user)
        if user.verifications.filter(status__in=EDITABLE).exists():
            return Response(verification_payload(user))
        if user.verifications.filter(status=V.PENDING).exists():
            raise ValidationError({"detail": "Заявка уже на проверке.", "code": "already_submitted"})

        verification = DriverVerification.objects.create(
            user=user,
            full_name_on_document=user.full_name,
            date_of_birth=user.date_of_birth,
            license_number=user.driver_license_number,
            license_issued_on=user.driver_license_issued,
            category_b_since=user.driving_since or user.driver_license_issued,
        )
        service.log(verification, VerificationEvent.Action.CREATED, user)
        service.sync_user_status(user)
        return Response(verification_payload(user), status=status.HTTP_201_CREATED)

    def patch(self, request):
        verification = open_verification(request.user)
        serializer = DriverVerificationSerializer(verification, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        now = timezone.now()
        # Без согласия сканы хранить нельзя (Закон № 99-З): отзыв удаляет их сразу.
        if "consent" in data:
            given = data.pop("consent")
            verification.consent_given_at = now if given else None
            verification.consent_version = settings.CONSENT_VERSION
            if not given:
                service.delete_documents(verification.documents.all())
        if "biometric_consent" in data:
            given = data.pop("biometric_consent")
            verification.biometric_consent_at = now if given else None
            if not given:
                service.delete_documents(verification.documents.filter(kind=SELFIE))
                service.delete_documents(LivenessFrame.objects.filter(check_run__verification=verification))
                verification.liveness_passed_at = None
        for field, value in data.items():
            setattr(verification, field, value)
        verification.save()
        return Response(verification_payload(request.user))


class DocumentView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "verification_upload"

    def get_throttles(self):
        # Лимит тратит только загрузка: просмотр превью и удаление — бесплатно.
        if self.request.method != "PUT":
            return []
        return super().get_throttles()

    def _kind(self, kind):
        if kind not in VerificationDocument.Kind.values:
            raise ValidationError({"detail": "Неизвестный тип документа.", "code": "bad_kind"})
        return kind

    def put(self, request, kind):
        kind = self._kind(kind)
        service.ensure_not_blocked(request.user)
        verification = open_verification(request.user)
        if not verification.consent_given_at:
            raise ValidationError(
                {"detail": "Сначала дайте согласие на обработку данных.", "code": "consent_required"}
            )
        if kind == SELFIE and not verification.biometric_consent_at:
            raise ValidationError(
                {"detail": "Сначала дайте согласие на обработку фото лица.", "code": "consent_required"}
            )
        existing = verification.documents.filter(kind=kind).first()
        if verification.status == V.NEEDS_FIX and existing and not existing.needs_reshoot:
            raise ValidationError({"detail": "Это фото модератор принял — переснимать не нужно."})

        upload = request.FILES.get("file")
        if not upload:
            raise ValidationError({"detail": "Прикрепите фото.", "code": "no_file"})
        content, meta = process_document_image(upload)

        demo = is_demo_request(request)
        if existing:
            existing.delete()  # файл удалит post_delete после коммита
        document = VerificationDocument(verification=verification, kind=kind, is_demo=demo, **meta)
        document.file.save(f"{kind}.jpg", content, save=True)
        # Загрузка — тоже активность по черновику: срок хранения считается от неё.
        verification.files_purged_at = None
        verification.save(update_fields=["files_purged_at", "updated_at"])
        service.log(verification, VerificationEvent.Action.DOCUMENT_UPLOADED, request.user, kind=kind)
        return Response(verification_payload(request.user))

    def get(self, request, kind):
        """Своё фото — только пока заявка не решена; одобренные документы клиенту не отдаём."""
        kind = self._kind(kind)
        document = get_object_or_404(
            VerificationDocument,
            verification__user=request.user,
            verification__status__in=(V.DRAFT, V.NEEDS_FIX, V.PENDING),
            kind=kind,
        )
        response = FileResponse(document.file.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "no-store"
        return response

    def delete(self, request, kind):
        kind = self._kind(kind)
        verification = open_verification(request.user)
        document = get_object_or_404(VerificationDocument, verification=verification, kind=kind)
        document.delete()
        return Response(verification_payload(request.user))


class SubmitView(APIView):
    def post(self, request):
        service.ensure_not_blocked(request.user)
        service.submit(open_verification(request.user))
        return Response(verification_payload(request.user))


class WithdrawConsentView(APIView):
    """Отзыв согласия: документы удаляются сразу, доступ к поездкам закрывается."""

    def post(self, request):
        service.withdraw_consent(request.user)
        return Response(verification_payload(request.user))


class LivenessStartView(APIView):
    """Начать проверку «живости»: сервер выбирает случайные движения и даёт две минуты."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "liveness"

    def post(self, request):
        service.ensure_not_blocked(request.user)
        verification = open_verification(request.user)
        if not verification.biometric_consent_at:
            raise ValidationError(
                {"detail": "Сначала дайте согласие на обработку фото лица.", "code": "consent_required"}
            )
        check = kyc.start_liveness(request.user, LivenessCheck.Purpose.KYC, verification=verification)
        return Response(liveness_payload(check), status=status.HTTP_201_CREATED)


class LivenessFramesView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, pk):
        check = get_object_or_404(
            LivenessCheck, pk=pk, user=request.user, purpose=LivenessCheck.Purpose.KYC
        )
        verification = open_verification(request.user)
        if check.verification_id != verification.id:
            raise ValidationError({"detail": "Проверка относится к другой заявке.", "code": "liveness_closed"})
        demo = is_demo_request(request)
        try:
            kyc.complete_liveness(check, request.FILES, demo=demo)
        except ValidationError:
            if check.status == LivenessCheck.Status.FAILED:
                service.log(verification, VerificationEvent.Action.LIVENESS_FAILED, request.user,
                            reason=check.failure_reason, motion=check.motion_score)
            raise
        verification.liveness_passed_at = check.completed_at
        verification.save(update_fields=["liveness_passed_at", "updated_at"])
        service.log(verification, VerificationEvent.Action.LIVENESS_PASSED, request.user,
                    motion=check.motion_score, demo=demo)
        return Response(verification_payload(request.user))


class DemoProfileView(APIView):
    """Только демо-режим: данные «из реестра ГАИ» на ФИО пользователя для заполнения анкеты."""

    def get(self, request):
        if not settings.KYC_DEMO_MODE:
            raise Http404
        from .demo import demo_persona

        return Response(demo_persona(request.user))

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import DriverVerification, LivenessFrame, VerificationEvent
from accounts.verification import delete_documents, log

V = DriverVerification.Status
DECIDED = (V.APPROVED, V.REJECTED, V.SUPERSEDED, V.REVOKED)
# Ждут водителя: если он бросил заявку, срок считается от последнего изменения.
ABANDONABLE = (V.DRAFT, V.NEEDS_FIX)


class Command(BaseCommand):
    help = (
        "Удаляет фото документов «Рули ID» после срока хранения "
        "(VERIFICATION_RETENTION_DAYS): у решённых заявок — от даты решения, "
        "у брошенных черновиков и доработок — от последнего изменения."
    )

    def handle(self, *args, **options):
        days = settings.VERIFICATION_RETENTION_DAYS
        now = timezone.now()
        cutoff = now - timedelta(days=days)
        expired = DriverVerification.objects.filter(files_purged_at__isnull=True).filter(
            Q(status__in=DECIDED, reviewed_at__lt=cutoff)
            | Q(status__in=ABANDONABLE, updated_at__lt=cutoff)
        )

        purged = files = 0
        for verification in expired:
            with transaction.atomic():
                deleted = delete_documents(verification.documents.all())
                deleted += delete_documents(LivenessFrame.objects.filter(check_run__verification=verification))
                verification.files_purged_at = now
                # Без updated_at: служебная очистка — не активность клиента.
                verification.save(update_fields=["files_purged_at"])
                log(verification, VerificationEvent.Action.FILES_PURGED, documents=deleted, retention_days=days)
            purged += 1
            files += deleted
        # Кадры лица перед поездками нужны только для разбора споров — тот же срок, от даты съёмки.
        trip_frames = delete_documents(
            LivenessFrame.objects.filter(check_run__purpose="trip", uploaded_at__lt=cutoff)
        )
        files += trip_frames
        self.stdout.write(f"Срок хранения {days} дн.: очищено заявок {purged}, удалено файлов {files}.")

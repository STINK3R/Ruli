import math
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from cars.models import Car
from rentals.models import Rental

from .chain import compute_seal, integrity_cache_key
from .models import GENESIS_HASH, Damage, Inspection, InspectionPhoto
from .quality import process_inspection_photo

REQUIRED_ANGLES = ("front", "rear", "left", "right")
SAME_DAMAGE_DISTANCE = 0.05  # в долях силуэта: ближе — это та же отметка
MAX_DAMAGE_MARKS = 12
CLEANLINESS_SCORE = {1: 5.0, 2: 3.0, 3: 1.0}


def _validate_marks(marks):
    if len(marks) > MAX_DAMAGE_MARKS:
        raise ValidationError({"damages": f"Не больше {MAX_DAMAGE_MARKS} отметок за осмотр."})
    clean = []
    for mark in marks:
        try:
            x, y = float(mark["x"]), float(mark["y"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError({"damages": "У отметки должны быть координаты x и y."})
        severity = mark.get("severity", Damage.Severity.SCRATCH)
        if not (0 <= x <= 1 and 0 <= y <= 1) or severity not in Damage.Severity.values:
            raise ValidationError({"damages": "Некорректная отметка повреждения."})
        clean.append({"x": x, "y": y, "severity": severity, "angle": mark.get("angle")})
    return clean


def _is_known(car, x, y):
    return any(
        math.dist((x, y), (damage.x, damage.y)) <= SAME_DAMAGE_DISTANCE
        for damage in car.damages.filter(status__in=Damage.ACTIVE)
    )


def _previous_rental(rental):
    """Последняя завершённая аренда этой машины до текущей брони — она отвечает за новое повреждение."""
    return (
        Rental.objects.filter(
            car_id=rental.car_id,
            status=Rental.Status.COMPLETED,
            finished_at__lt=rental.reserved_at,
        )
        .exclude(pk=rental.pk)
        .order_by("-finished_at")
        .first()
    )


def create_inspection(rental, user, kind, photos, marks=(), cleanliness=None, confirmed=False, lat=None, lng=None):
    """Принимает осмотр, ставит отметки повреждений и запечатывает акт в цепочку машины."""
    if kind not in Inspection.Kind.values:
        raise ValidationError({"kind": "Тип осмотра: start или finish."})
    expected_status = Rental.Status.RESERVED if kind == Inspection.Kind.START else Rental.Status.ACTIVE
    if rental.status != expected_status:
        raise ValidationError(
            "Осмотр перед поездкой делается до старта, финальный — перед завершением."
        )
    if cleanliness is not None and cleanliness not in Inspection.Cleanliness.values:
        raise ValidationError({"cleanliness": "Оценка чистоты: 1, 2 или 3."})

    required = list(REQUIRED_ANGLES)
    if kind == Inspection.Kind.START and cleanliness == Inspection.Cleanliness.DIRTY:
        required.append("interior")
    missing = [angle for angle in required if angle not in photos]
    if missing:
        labels = ", ".join(InspectionPhoto.Angle(angle).label.lower() for angle in missing)
        raise ValidationError({"photos": f"Не хватает фото: {labels}.", "missing": missing})
    marks = _validate_marks(list(marks))

    # Тяжёлая обработка фото — до блокировки, чтобы не держать строку машины.
    processed = {angle: process_inspection_photo(upload, angle) for angle, upload in photos.items()}

    with transaction.atomic():
        car = Car.objects.select_for_update().get(pk=rental.car_id)
        if Inspection.objects.filter(rental=rental, kind=kind).exists():
            raise ValidationError("Этот осмотр уже запечатан.")

        last = Inspection.objects.filter(car=car).order_by("-created_at", "-id").first()
        inspection = Inspection.objects.create(
            rental=rental,
            car=car,
            user=user,
            kind=kind,
            created_at=timezone.now(),
            latitude=lat,
            longitude=lng,
            cleanliness=cleanliness,
            confirmed_as_passport=confirmed,
            prev_hash=last.seal_hash if last else GENESIS_HASH,
            seal_hash=f"pending-{uuid.uuid4().hex}",
        )
        saved_photos = {}
        for angle, (content, meta) in processed.items():
            photo = InspectionPhoto(inspection=inspection, angle=angle, **meta)
            photo.image.save(f"{angle}.webp", ContentFile(content), save=True)
            saved_photos[angle] = photo

        responsible = rental if kind == Inspection.Kind.FINISH else _previous_rental(rental)
        new_damages = []
        for mark in marks:
            # Уже есть в паспорте — не новое повреждение ни до, ни после поездки:
            # повторная отметка не делает текущую аренду ответственной.
            if _is_known(car, mark["x"], mark["y"]):
                continue
            new_damages.append(
                Damage.objects.create(
                    car=car,
                    x=mark["x"],
                    y=mark["y"],
                    severity=mark["severity"],
                    photo=saved_photos.get(mark["angle"]),
                    first_seen=inspection,
                    responsible_rental=responsible,
                    status=Damage.Status.NEW,
                )
            )

        inspection.seal_hash = compute_seal(inspection)
        inspection.save(update_fields=["seal_hash"])
        # Кэш проверки цепочки ещё не знает о новом акте.
        transaction.on_commit(lambda: cache.delete(integrity_cache_key(car.pk)))

        if kind == Inspection.Kind.START and cleanliness == Inspection.Cleanliness.DIRTY:
            _apply_cleanliness_guarantee(rental, car, user, has_interior="interior" in saved_photos)
    return inspection, new_damages


def signature_guarantee_available(user, exclude_rental_id=None):
    """Гарантию Signature можно получить не чаще раза в неделю — защита от злоупотреблений."""
    week_ago = timezone.now() - timedelta(days=7)
    used = Rental.objects.filter(user=user, compensation_minutes__gt=0, reserved_at__gte=week_ago)
    if exclude_rental_id is not None:
        used = used.exclude(pk=exclude_rental_id)
    return not used.exists()


def _apply_cleanliness_guarantee(rental, car, user, has_interior):
    """Гарантия Signature: грязная машина в оклейке — первые минуты поездки бесплатно."""
    car.needs_cleaning = True
    car.save(update_fields=["needs_cleaning"])
    if not car.is_signature or not has_interior:
        return
    if not signature_guarantee_available(user, exclude_rental_id=rental.pk):
        return
    rental.compensation_minutes = settings.SIGNATURE_COMPENSATION_MINUTES
    rental.save(update_fields=["compensation_minutes"])


def cleanliness_score(car):
    marks = list(
        Inspection.objects.filter(car=car, kind=Inspection.Kind.START, cleanliness__isnull=False)
        .order_by("-created_at")
        .values_list("cleanliness", flat=True)[:5]
    )
    if not marks:
        return None
    return round(sum(CLEANLINESS_SCORE[mark] for mark in marks) / len(marks), 1)


def open_claim(damage, now=None):
    """Претензия к ответственной поездке: только в течение 24 часов после неё.

    Если повреждение впервые отмечено ещё до начала этой поездки, претензия
    отклоняется автоматически — клиент не отвечает за то, что было в паспорте.
    """
    now = now or timezone.now()
    rental = damage.responsible_rental
    if rental is None or rental.finished_at is None:
        raise ValidationError("Не удалось определить ответственную поездку.")
    if rental.started_at and damage.first_seen.created_at < rental.started_at:
        damage.status = Damage.Status.DISPUTED
        damage.claim_note = (
            f"Отклонено автоматически: повреждение было в паспорте до поездки "
            f"(акт #{damage.first_seen.seal_short})."
        )
        damage.save(update_fields=["status", "claim_note"])
        return damage
    window = timedelta(hours=settings.DAMAGE_CLAIM_WINDOW_HOURS)
    if now > rental.finished_at + window:
        raise ValidationError(
            f"Окно претензий ({settings.DAMAGE_CLAIM_WINDOW_HOURS} ч) закрыто — ущерб за счёт оператора."
        )
    damage.status = Damage.Status.CONFIRMED
    damage.claim_note = f"Вина подтверждена: поездка #{rental.pk}, претензия в пределах 24 часов."
    damage.save(update_fields=["status", "claim_note"])
    return damage

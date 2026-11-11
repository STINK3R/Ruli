"""Цепочка хэшей актов осмотра: подмену задним числом видно по разрыву цепочки."""

import hashlib
import json

from .models import GENESIS_HASH, Inspection


def _round(value, digits):
    return None if value is None else round(value, digits)


def seal_payload(inspection):
    photos = sorted([photo.angle, photo.sha256] for photo in inspection.photos.all())
    damages = sorted(
        [_round(damage.x, 3), _round(damage.y, 3), damage.severity]
        for damage in inspection.first_damages.all()
    )
    payload = {
        "prev": inspection.prev_hash,
        "car": inspection.car_id,
        "rental": inspection.rental_id,
        "user": inspection.user_id,
        "kind": inspection.kind,
        "at": inspection.created_at.isoformat(),
        "lat": _round(inspection.latitude, 6),
        "lon": _round(inspection.longitude, 6),
        "cleanliness": inspection.cleanliness,
        "confirmed": inspection.confirmed_as_passport,
        "photos": photos,
        "damages": damages,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_seal(inspection):
    return hashlib.sha256(seal_payload(inspection).encode("utf-8")).hexdigest()


def integrity_cache_key(car_id):
    """Ключ кэша проверки цепочки: им пользуются и паспорт, и запечатывание нового акта."""
    return f"passport:verify:{car_id}"


def file_sha256(field_file):
    digest = hashlib.sha256()
    with field_file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_chain(car):
    """Пересчитывает хэши файлов и печати всех актов машины по порядку."""
    previous = GENESIS_HASH
    inspections = (
        Inspection.objects.filter(car=car)
        .order_by("created_at", "id")
        .prefetch_related("photos", "first_damages")
    )
    checked = 0
    for inspection in inspections:
        for photo in inspection.photos.all():
            try:
                actual = file_sha256(photo.image)
            except (FileNotFoundError, ValueError, OSError):
                actual = None
            if actual != photo.sha256:
                return _broken(checked, inspection, "photo_modified")
        if inspection.prev_hash != previous:
            return _broken(checked, inspection, "link_broken")
        if compute_seal(inspection) != inspection.seal_hash:
            return _broken(checked, inspection, "record_modified")
        previous = inspection.seal_hash
        checked += 1
    return {"ok": True, "checked": checked, "broken_at": None, "reason": None}


REASONS = {
    "photo_modified": "фото акта изменено после запечатывания",
    "record_modified": "данные акта изменены после запечатывания",
    "link_broken": "акт выпал из цепочки или вставлен задним числом",
}


def _broken(checked, inspection, reason):
    return {
        "ok": False,
        "checked": checked,
        "broken_at": inspection.pk,
        "broken_seal": inspection.seal_short,
        "reason": reason,
        "reason_text": REASONS[reason],
    }

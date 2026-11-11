"""Демо-история поездок с актами осмотра, чтобы паспорт кузова и «Допуск Плюс» работали сразу."""

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageDraw

from cars.models import Car
from rentals.models import Rental

from .chain import compute_seal
from .models import GENESIS_HASH, Damage, Inspection, InspectionPhoto
from .quality import measure

BODY_RGB = {
    "белый": (236, 238, 242),
    "серебристый": (196, 202, 212),
    "серый": (128, 136, 148),
    "чёрный": (38, 42, 50),
    "черный": (38, 42, 50),
    "синий": (47, 100, 224),
    "красный": (200, 56, 46),
}
ANGLES = ("front", "rear", "left", "right")

# (номер машины, дней назад, минут в пути, чистота на старте, известные повреждения)
DEMO_TRIPS = [
    ("8743 AB-7", 52, 18, 1, [(0.5, 0.05, "scratch")]),
    ("6607 TA-7", 43, 34, 2, [(0.12, 0.46, "dent")]),
    ("2914 IB-7", 31, 12, 1, []),
    ("7715 HB-7", 23, 47, 1, [(0.86, 0.9, "scratch"), (0.42, 0.2, "crack")]),
    ("3521 EX-7", 12, 25, 2, [(0.15, 0.7, "scratch")]),
    ("1056 KE-7", 5, 63, 1, [(0.8, 0.12, "dent")]),
]


def demo_photo(car, angle):
    """Синтетическое фото ракурса: силуэт машины в её цвете на фоне двора с шумом."""
    width, height = 960, 640
    background = Image.new("RGB", (width, height), (214, 210, 202))
    noise = Image.effect_noise((width, height), 48).convert("RGB")
    image = Image.blend(background, noise, 0.14)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 470, width, height], fill=(96, 94, 90))

    body = BODY_RGB.get((car.color or "").lower(), (128, 136, 148))
    dark = tuple(max(0, c - 60) for c in body)
    glass = (70, 92, 120)
    if angle in ("left", "right"):
        draw.rounded_rectangle([150, 300, 810, 455], radius=50, fill=body, outline=dark, width=5)
        draw.rounded_rectangle([300, 215, 640, 315], radius=40, fill=body, outline=dark, width=5)
        draw.rectangle([330, 235, 460, 300], fill=glass)
        draw.rectangle([480, 235, 610, 300], fill=glass)
        wheels = [(210, 400, 330, 520), (630, 400, 750, 520)]
    else:
        draw.rounded_rectangle([250, 280, 710, 460], radius=40, fill=body, outline=dark, width=5)
        draw.rounded_rectangle([310, 190, 650, 300], radius=30, fill=glass, outline=dark, width=5)
        draw.rectangle([280, 330, 360, 360], fill=(250, 240, 200) if angle == "front" else (210, 40, 30))
        draw.rectangle([600, 330, 680, 360], fill=(250, 240, 200) if angle == "front" else (210, 40, 30))
        wheels = [(270, 430, 350, 520), (610, 430, 690, 520)]
    for box in wheels:
        draw.ellipse(box, fill=(25, 25, 28), outline=(70, 70, 75), width=6)
    draw.rectangle([400, 420, 560, 455], fill=(250, 250, 250), outline=(20, 20, 20), width=3)
    draw.text((418, 428), car.license_plate, fill=(20, 20, 20))
    draw.text((24, 20), f"{angle.upper()}  {car.license_plate}", fill=(30, 30, 30))

    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=82)
    content = buffer.getvalue()
    brightness, sharpness = measure(image)
    return content, {
        "sha256": hashlib.sha256(content).hexdigest(),
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 2),
    }


def _seal_inspection(rental, car, user, kind, at, cleanliness, marks=()):
    last = Inspection.objects.filter(car=car).order_by("-created_at", "-id").first()
    inspection = Inspection.objects.create(
        rental=rental,
        car=car,
        user=user,
        kind=kind,
        created_at=at,
        latitude=car.latitude,
        longitude=car.longitude,
        cleanliness=cleanliness,
        confirmed_as_passport=kind == Inspection.Kind.FINISH,
        prev_hash=last.seal_hash if last else GENESIS_HASH,
        seal_hash=f"pending-{uuid.uuid4().hex}",
    )
    photos = {}
    for angle in ANGLES:
        content, meta = demo_photo(car, angle)
        photo = InspectionPhoto(inspection=inspection, angle=angle, **meta)
        photo.image.save(f"{angle}.webp", ContentFile(content), save=True)
        photos[angle] = photo
    for x, y, severity in marks:
        Damage.objects.create(
            car=car,
            x=x,
            y=y,
            severity=severity,
            photo=photos["front" if y < 0.5 else "rear"],
            first_seen=inspection,
            status=Damage.Status.KNOWN,
        )
    inspection.seal_hash = compute_seal(inspection)
    inspection.save(update_fields=["seal_hash"])
    return inspection


def seed_history(user, stdout=None):
    """История поездок клиента demo с запечатанными актами — только на пустой базе актов."""
    if Inspection.objects.exists():
        return 0
    from rentals.services import calculate_trip_cost

    now = timezone.now()
    created = 0
    for plate, days_ago, minutes, cleanliness, marks in DEMO_TRIPS:
        car = Car.objects.select_related("tariff").filter(license_plate=plate).first()
        if car is None:
            continue
        reserved = now - timedelta(days=days_ago, hours=3)
        started = reserved + timedelta(minutes=6)
        finished = started + timedelta(minutes=minutes)
        tariff = car.tariff
        rental = Rental.objects.create(
            user=user,
            car=car,
            status=Rental.Status.COMPLETED,
            price_per_minute_at_booking=tariff.price_per_minute,
            waiting_price_per_minute_at_booking=tariff.waiting_price_per_minute,
            price_per_hour_at_booking=tariff.price_per_hour,
            price_per_day_at_booking=tariff.price_per_day,
            start_latitude=car.latitude,
            start_longitude=car.longitude,
            end_latitude=car.latitude,
            end_longitude=car.longitude,
            started_at=started,
            finished_at=finished,
            waiting_cost=Decimal("0.00"),
        )
        Rental.objects.filter(pk=rental.pk).update(reserved_at=reserved)
        rental.refresh_from_db()
        rental.total_cost = calculate_trip_cost(rental)
        rental.save(update_fields=["total_cost"])

        _seal_inspection(rental, car, user, Inspection.Kind.START, started - timedelta(minutes=2), cleanliness, marks)
        _seal_inspection(rental, car, user, Inspection.Kind.FINISH, finished + timedelta(minutes=1), None)
        car.last_cleaned_at = reserved - timedelta(days=1)
        car.save(update_fields=["last_cleaned_at"])
        created += 1
    if stdout:
        stdout.write(f"История: {created} поездок с актами осмотра в цепочке SHA-256.")
    return created

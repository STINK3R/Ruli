"""Помощники для тестов: водитель с одобренной заявкой и тестовые изображения."""

from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image, ImageDraw

from .models import DriverVerification, LicenseRegistryRecord, User
from .verification import normalize_license, sync_user_status

_counter = {"value": 0}


def make_driver(
    username="driver",
    dob=date(1990, 1, 1),
    driving_since=date(2010, 1, 1),
    license_number=None,
    expires=date(2035, 1, 1),
    **fields,
):
    _counter["value"] += 1
    number = license_number or f"5AB {100000 + _counter['value']:06d}"
    now = timezone.now()
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123",
        first_name=fields.pop("first_name", "Иван"),
        last_name=fields.pop("last_name", "Иванов"),
        phone_number=fields.pop("phone_number", f"+3752970{_counter['value']:05d}"),
        phone_verified_at=now,
        **fields,
    )
    DriverVerification.objects.create(
        user=user,
        status=DriverVerification.Status.APPROVED,
        source=DriverVerification.Source.SEED,
        full_name_on_document="Иванов Иван",
        date_of_birth=dob,
        license_number=number,
        license_number_normalized=normalize_license(number),
        license_issued_on=driving_since,
        license_expires_on=expires,
        category_b_since=driving_since,
        consent_given_at=now,
        biometric_consent_at=now,
        liveness_passed_at=now,
        submitted_at=now,
        reviewed_at=now,
    )
    sync_user_status(user)
    user.refresh_from_db()
    return user


def registry_for(number, full_name, dob, issued, expires, category_b=None, **extra):
    """Запись «реестра ГАИ» под тестовую заявку."""
    return LicenseRegistryRecord.objects.create(
        number_normalized=normalize_license(number),
        full_name=full_name,
        date_of_birth=dob,
        issued_on=issued,
        expires_on=expires,
        category_b_since=category_b or issued,
        **extra,
    )


def image_file(name="photo.jpg", size=(800, 600), kind="noise", fmt="JPEG", exif=None):
    if kind == "noise":
        image = Image.effect_noise(size, 60).convert("RGB")
    elif kind == "scene":
        # Кадр с крупной деталью в случайном месте — как голова, повёрнутая в разные стороны.
        image = Image.effect_noise(size, 25).convert("RGB")
        draw = ImageDraw.Draw(image)
        _counter["frame"] = _counter.get("frame", 0) + 1
        step = _counter["frame"]
        x = (step * 97) % (size[0] // 2)
        y = (step * 53) % (size[1] // 3)
        draw.ellipse((x, y, x + size[0] // 2, y + size[1] // 2), fill=(250, 235, 220))
    elif kind == "dark":
        image = Image.new("RGB", size, (8, 8, 8))
    else:  # flat — однотонная серая картинка без деталей
        image = Image.new("RGB", size, (140, 140, 140))
    buffer = BytesIO()
    params = {"exif": exif} if exif is not None else {}
    image.save(buffer, fmt, **params)
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

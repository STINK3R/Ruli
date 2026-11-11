"""Проверки «Рули ID», которые не дают пройти с выдуманными данными.

1. Телефон — одноразовый код из SMS.
2. Личный номер паспорта РБ — контрольная цифра и зашитые в номер пол и дата рождения.
3. Реестр ВУ (имитация ГАИ) — номер существует, принадлежит этому человеку и не лишён.
4. «Живость» — случайные движения перед камерой за две минуты, кадры видит модератор.

Без нейросетей: каждое правило можно объяснить и проверить руками.
"""

import hashlib
import hmac
import logging
import random
import re
import secrets
from datetime import date, timedelta
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from PIL import Image, ImageChops, ImageStat
from rest_framework.exceptions import ValidationError

from .models import LicenseRegistryRecord, LivenessCheck, LivenessFrame, PhoneCode

logger = logging.getLogger("ruli.sms")

# ---------- Телефон ----------

PHONE_RE = re.compile(r"^\+375(25|29|33|44)\d{7}$")


def normalize_phone(value):
    digits = re.sub(r"[^\d+]", "", value or "")
    if digits.startswith("80") and len(digits) == 11:  # 80 29 123-45-67 → +375 29 …
        digits = "+375" + digits[2:]
    elif digits.startswith("375"):
        digits = "+" + digits
    return digits


def _hash_code(phone, code):
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def mask_phone(phone):
    return f"{phone[:6]} ••• •• {phone[-2:]}" if phone and len(phone) > 8 else phone


def send_sms(phone, text):
    """Точка подключения SMS-шлюза. В демо-режиме код показывается в приложении."""
    logger.info("SMS на %s: %s", mask_phone(phone), text)


def send_phone_code(user):
    phone = user.phone_number
    if not phone:
        raise ValidationError({"detail": "Укажите номер телефона в профиле.", "code": "no_phone"})
    if not PHONE_RE.match(phone):
        raise ValidationError(
            {"detail": "Нужен белорусский мобильный номер: +375 29/33/44/25 …", "code": "bad_phone"}
        )
    if user.phone_verified:
        raise ValidationError({"detail": "Номер уже подтверждён.", "code": "already_verified"})

    now = timezone.now()
    last = user.phone_codes.filter(phone=phone).first()
    cooldown = settings.PHONE_CODE_RESEND_SECONDS
    if last and (now - last.created_at).total_seconds() < cooldown:
        wait = cooldown - int((now - last.created_at).total_seconds())
        raise ValidationError(
            {"detail": f"Новый код можно запросить через {wait} с.", "code": "cooldown", "resend_in": wait}
        )

    code = f"{secrets.randbelow(10 ** 6):06d}"
    user.phone_codes.filter(used_at__isnull=True).update(used_at=now)  # старые коды больше не действуют
    PhoneCode.objects.create(
        user=user,
        phone=phone,
        code_hash=_hash_code(phone, code),
        expires_at=now + timedelta(seconds=settings.PHONE_CODE_TTL_SECONDS),
    )
    send_sms(phone, f"Рули: код {code}. Никому его не сообщайте.")
    payload = {
        "sent_to": mask_phone(phone),
        "expires_in": settings.PHONE_CODE_TTL_SECONDS,
        "resend_in": cooldown,
    }
    if settings.SMS_DEMO_MODE:
        payload["demo_code"] = code
    return payload


def confirm_phone_code(user, code):
    # Без общей транзакции: счётчик неверных попыток должен сохраниться, даже когда мы бросаем ошибку.
    code = re.sub(r"\D", "", str(code or ""))
    record = PhoneCode.objects.filter(user=user, phone=user.phone_number, used_at__isnull=True).first()
    if record is None or record.expires_at < timezone.now():
        raise ValidationError({"detail": "Код устарел — запросите новый.", "code": "code_expired"})
    if record.attempts >= settings.PHONE_CODE_MAX_ATTEMPTS:
        raise ValidationError({"detail": "Слишком много попыток — запросите новый код.", "code": "code_locked"})

    if not hmac.compare_digest(record.code_hash, _hash_code(record.phone, code)):
        PhoneCode.objects.filter(pk=record.pk).update(attempts=F("attempts") + 1)
        record.refresh_from_db(fields=["attempts"])
        left = max(0, settings.PHONE_CODE_MAX_ATTEMPTS - record.attempts)
        raise ValidationError(
            {"detail": f"Неверный код. Осталось попыток: {left}.", "code": "code_wrong", "attempts_left": left}
        )

    now = timezone.now()
    with transaction.atomic():
        # Один код — одно подтверждение, даже при двух одновременных запросах.
        if not PhoneCode.objects.filter(pk=record.pk, used_at__isnull=True).update(used_at=now):
            raise ValidationError({"detail": "Код уже использован — запросите новый.", "code": "code_expired"})
        user.phone_verified_at = now
        user.save(update_fields=["phone_verified_at"])
    return user


# ---------- Личный номер (паспорт и ID-карта РБ) ----------

# 3 150589 A 001 PB 1: пол и век · дата рождения ДДММГГ · регион · порядковый номер · гражданство · контроль.
PERSONAL_NUMBER_RE = re.compile(r"^([1-6])(\d{2})(\d{2})(\d{2})([ABCHKEM])(\d{3})([A-Z]{2})(\d)$")
CENTURY = {1: 1800, 2: 1800, 3: 1900, 4: 1900, 5: 2000, 6: 2000}
CYRILLIC_TWINS = str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX")


def normalize_personal_number(value):
    return re.sub(r"\s", "", (value or "").upper().translate(CYRILLIC_TWINS))


def check_digit(text):
    """Контрольная цифра по ICAO 9303 (как в машиночитаемой зоне паспорта): веса 7, 3, 1."""
    total = 0
    for index, char in enumerate(text):
        value = int(char) if char.isdigit() else ord(char) - 55  # A = 10 … Z = 35
        total += value * (7, 3, 1)[index % 3]
    return total % 10


def make_personal_number(birth, sex="m", region="H", serial=1, citizenship="PB"):
    """Корректный личный номер для демо-данных и тестов."""
    century = (birth.year // 100) * 100
    first = {1800: 1, 1900: 3, 2000: 5}[century] + (1 if sex == "f" else 0)
    body = f"{first}{birth:%d%m%y}{region}{serial:03d}{citizenship}"
    return body + str(check_digit(body))


def parse_personal_number(value):
    """Разбор номера: (дата рождения, пол, гражданство) или ValueError с понятной причиной."""
    number = normalize_personal_number(value)
    match = PERSONAL_NUMBER_RE.match(number)
    if not match:
        raise ValueError("Личный номер — 14 знаков: 7 цифр, буква, 3 цифры, 2 буквы, цифра.")
    if check_digit(number[:13]) != int(number[13]):
        raise ValueError("В личном номере ошибка — сверьте его с документом.")
    sex_century, day, month, year = (int(match.group(i)) for i in range(1, 5))
    try:
        birth = date(CENTURY[sex_century] + year, month, day)
    except ValueError:
        raise ValueError("В личном номере закодирована несуществующая дата.")
    return birth, ("f" if sex_century % 2 == 0 else "m"), match.group(7)


# ---------- Реестр ВУ (имитация ГАИ) ----------

def _name_key(value):
    return re.sub(r"\s+", " ", (value or "").lower().replace("ё", "е")).strip()


def registry_lookup(number_normalized):
    return LicenseRegistryRecord.objects.filter(number_normalized=number_normalized).first()


def registry_checks(verification, normalized):
    """Сверка анкеты с записью реестра. Только для прав РБ — иностранные проверяет модератор."""
    if verification.license_country != "BY":
        return [("foreign_license", "warn", "Иностранные права: в реестре ГАИ не проверить — сверьте вручную.")]

    record = registry_lookup(normalized)
    if record is None:
        return [("registry_not_found", "fail", "Удостоверение с таким номером не найдено в реестре ГАИ.")]

    checks = []
    if record.status == LicenseRegistryRecord.Status.SUSPENDED:
        until = f" до {record.suspended_until:%d.%m.%Y}" if record.suspended_until else ""
        checks.append(("registry_suspended", "fail", f"По данным ГАИ водитель лишён права управления{until}."))
    elif record.status == LicenseRegistryRecord.Status.INVALID:
        checks.append(("registry_invalid", "fail", "По данным ГАИ удостоверение недействительно."))

    v = verification
    surname = _name_key(record.full_name).split(" ")[0]
    if surname and surname not in _name_key(v.full_name_on_document):
        checks.append(("registry_name", "fail", "ФИО не совпадает с владельцем удостоверения."))
    if v.date_of_birth and record.date_of_birth != v.date_of_birth:
        checks.append(("registry_birth", "fail", "Дата рождения не совпадает с данными ГАИ."))
    if (v.license_issued_on and record.issued_on != v.license_issued_on) or (
        v.license_expires_on and record.expires_on != v.license_expires_on
    ):
        checks.append(("registry_dates", "fail", "Даты выдачи или срока действия не совпадают с данными ГАИ."))
    if "B" not in record.categories.upper().replace("В", "B"):
        checks.append(("registry_category", "fail", "В удостоверении нет категории B."))
    elif record.category_b_since and v.category_b_since and record.category_b_since != v.category_b_since:
        checks.append(("registry_category_date", "warn", "Дата открытия категории B отличается от данных ГАИ."))
    return checks


def registry_blocks(user):
    """Права одобренного водителя потом лишили или аннулировали — поездки закрываются сразу."""
    if not user.license_key:
        return None
    record = registry_lookup(user.license_key)
    if record and record.status != LicenseRegistryRecord.Status.VALID:
        return record
    return None


# ---------- «Живость» ----------

STEP_LABELS = {
    "center": "Посмотрите прямо в камеру",
    "turn_left": "Медленно поверните голову влево",
    "turn_right": "Медленно поверните голову вправо",
    "look_up": "Поднимите подбородок",
    "smile": "Улыбнитесь",
    "closer": "Приблизьте лицо к камере",
}
MOVES = [step for step in STEP_LABELS if step != "center"]


def describe_steps(steps):
    return [{"code": step, "label": STEP_LABELS[step]} for step in steps]


def start_liveness(user, purpose, verification=None):
    moves = 3 if purpose == LivenessCheck.Purpose.KYC else 1
    steps = ["center", *random.sample(MOVES, moves)]
    now = timezone.now()
    # Незавершённые проверки больше не принимают кадры: действует только последняя.
    user.liveness_checks.filter(status=LivenessCheck.Status.PENDING, purpose=purpose).update(
        status=LivenessCheck.Status.EXPIRED
    )
    return LivenessCheck.objects.create(
        user=user,
        verification=verification,
        purpose=purpose,
        steps=steps,
        expires_at=now + timedelta(seconds=settings.LIVENESS_TTL_SECONDS),
    )


def _thumbnail(content):
    image = Image.open(BytesIO(content.read())).convert("L")
    content.seek(0)
    return image.resize((48, 48))


def motion_between(frames):
    """Насколько кадры движений отличаются от кадра «прямо в камеру»: средняя разница яркости 0–255.

    Берётся самое заметное движение: улыбка меняет кадр мало, поворот головы — сильно.
    Если перед камерой держат фото или экран, все кадры почти одинаковые.
    """
    center = frames["center"]
    diffs = [
        ImageStat.Stat(ImageChops.difference(center, frame)).mean[0]
        for step, frame in frames.items()
        if step != "center"
    ]
    return round(max(diffs), 2) if diffs else 0.0


def _fail(check, reason):
    check.status = LivenessCheck.Status.FAILED
    check.failure_reason = reason
    check.completed_at = timezone.now()
    check.save(update_fields=["status", "failure_reason", "completed_at"])
    raise ValidationError({"detail": reason, "code": "liveness_failed"})


def complete_liveness(check, files, demo=False):
    """Принимает кадры по шагам. Возвращает пройденную проверку или бросает ValidationError."""
    from .images import process_document_image

    if check.status != LivenessCheck.Status.PENDING:
        raise ValidationError({"detail": "Эта проверка уже завершена — начните заново.", "code": "liveness_closed"})
    if timezone.now() > check.expires_at:
        check.status = LivenessCheck.Status.EXPIRED
        check.save(update_fields=["status"])
        raise ValidationError({"detail": "Время на съёмку вышло — начните заново.", "code": "liveness_expired"})
    if demo and not settings.KYC_DEMO_MODE:
        raise ValidationError({"detail": "Демо-кадры отключены.", "code": "demo_disabled"})

    missing = [step for step in check.steps if step not in files]
    if missing:
        raise ValidationError({"detail": "Сняты не все движения.", "code": "liveness_incomplete"})

    processed, thumbs, hashes = {}, {}, set()
    for step in check.steps:
        content, meta = process_document_image(files[step])
        if meta["sha256"] in hashes:
            _fail(check, "Одинаковые кадры — повторите и выполните движения.")
        hashes.add(meta["sha256"])
        processed[step] = (content, meta)
        thumbs[step] = _thumbnail(content)

    score = motion_between(thumbs)
    check.motion_score = score
    check.is_demo = demo
    if score < settings.LIVENESS_MIN_MOTION:
        check.save(update_fields=["motion_score", "is_demo"])
        _fail(check, "Движения не видно — похоже на фото или экран. Повторите перед камерой.")

    with transaction.atomic():
        for step, (content, meta) in processed.items():
            frame = LivenessFrame(check_run=check, step=step, sha256=meta["sha256"])
            frame.file.save(f"{step}.jpg", content, save=True)
        check.status = LivenessCheck.Status.PASSED
        check.completed_at = timezone.now()
        check.save(update_fields=["status", "completed_at", "motion_score", "is_demo"])
    return check

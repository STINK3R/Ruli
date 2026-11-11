"""Демо-пользователи с разными уровнями «Рули ID» — чтобы на защите показать всю лестницу."""

import random
from datetime import date

from django.conf import settings
from django.utils import timezone

from .kyc import make_personal_number
from .models import DriverVerification, LicenseRegistryRecord, User
from .verification import LONG_LICENSE_SINCE, add_years, normalize_license, sync_user_status

DEMO_USERS = [
    {
        "username": "admin",
        "password": "admin12345",
        "superuser": True,
        "sex": "f",
        "fields": {
            "email": "admin@ruli.by",
            "first_name": "Ирина",
            "last_name": "Котович",
            "phone_number": "+375339990011",
        },
        "license": {
            "date_of_birth": date(1988, 2, 11),
            "license_number": "7MK 845210",
            "license_issued_on": date(2018, 3, 1),
            "license_expires_on": date(2028, 3, 1),
            "category_b_since": date(2008, 5, 20),
        },
    },
    {
        # Опытный клиент: после истории поездок получает «Допуск Плюс».
        "username": "demo",
        "password": "demo12345",
        "fields": {
            "email": "demo@ruli.by",
            "first_name": "Алексей",
            "last_name": "Демидович",
            "patronymic": "Игоревич",
            "phone_number": "+375291234567",
        },
        "license": {
            "date_of_birth": date(1994, 5, 12),
            "license_number": "5AB 123456",
            "license_issued_on": date(2022, 6, 20),
            "license_expires_on": date(2032, 6, 20),
            "category_b_since": date(2014, 7, 1),
        },
    },
    {
        # Молодой водитель: эконом и комфорт открыты, бизнес и премиум — с датой открытия.
        "username": "novice",
        "password": "novice12345",
        "sex": "f",
        "fields": {
            "email": "novice@ruli.by",
            "first_name": "Ксения",
            "last_name": "Новик",
            "phone_number": "+375447654321",
        },
        "license": {
            "date_of_birth": date(2006, 3, 15),
            "license_number": "3HP 556017",
            "license_issued_on": date(2025, 4, 10),
            "license_expires_on": date(2045, 4, 10),
            "category_b_since": date(2025, 4, 10),
        },
    },
    {
        # Новичок без проверки — на нём показывают подачу документов.
        "username": "newbie",
        "password": "newbie12345",
        "fields": {
            "email": "newbie@ruli.by",
            "first_name": "Иван",
            "last_name": "Новый",
            "phone_number": "+375255550101",
        },
        "license": None,
    },
]

# Записи «реестра ГАИ», на которых показывают отказ: лишение прав и аннулированное удостоверение.
REGISTRY_EXAMPLES = [
    {
        "number": "6KX 000777",
        "full_name": "Лишенко Пётр Сергеевич",
        "date_of_birth": date(1987, 9, 3),
        "issued_on": date(2017, 4, 12),
        "expires_on": date(2027, 4, 12),
        "status": LicenseRegistryRecord.Status.SUSPENDED,
        "suspended_until": date(2027, 1, 15),
        "note": "Пример: лишение права управления",
    },
    {
        "number": "1AB 000013",
        "full_name": "Утерин Олег Викторович",
        "date_of_birth": date(1992, 1, 21),
        "issued_on": date(2019, 8, 1),
        "expires_on": date(2029, 8, 1),
        "status": LicenseRegistryRecord.Status.INVALID,
        "note": "Пример: удостоверение заявлено утерянным",
    },
]


def registry_record(number, full_name, date_of_birth, issued_on, expires_on, category_b_since=None, **extra):
    record, _ = LicenseRegistryRecord.objects.update_or_create(
        number_normalized=normalize_license(number),
        defaults={
            "full_name": full_name,
            "date_of_birth": date_of_birth,
            "issued_on": issued_on,
            "expires_on": expires_on,
            "category_b_since": category_b_since or issued_on,
            "categories": "B",
            **extra,
        },
    )
    return record


def ensure_registry():
    for example in REGISTRY_EXAMPLES:
        registry_record(**example)


def ensure_demo_users(stdout=None):
    ensure_registry()
    users = {}
    for spec in DEMO_USERS:
        user = User.objects.filter(username=spec["username"]).first()
        if user is None:
            create = User.objects.create_superuser if spec.get("superuser") else User.objects.create_user
            user = create(username=spec["username"], password=spec["password"], **spec["fields"])
            if stdout:
                stdout.write(f"Создан пользователь {spec['username']} / {spec['password']}")
        users[spec["username"]] = user

        # Телефоны демо-аккаунтов считаются подтверждёнными: SMS на защите не нужна.
        if not user.phone_number and spec["fields"].get("phone_number"):
            user.phone_number = spec["fields"]["phone_number"]
        if user.phone_number and not user.phone_verified_at:
            user.phone_verified_at = timezone.now()
            user.save(update_fields=["phone_number", "phone_verified_at"])

        license_data = spec["license"]
        if license_data is None:
            continue
        registry_record(
            license_data["license_number"],
            user.full_name or user.get_full_name(),
            license_data["date_of_birth"],
            license_data["license_issued_on"],
            license_data["license_expires_on"],
            license_data["category_b_since"],
        )
        has_seed = user.verifications.filter(
            status=DriverVerification.Status.APPROVED, category_b_since__isnull=False
        ).exists()
        if has_seed:
            continue

        now = timezone.now()
        user.verifications.filter(status=DriverVerification.Status.APPROVED).update(
            status=DriverVerification.Status.SUPERSEDED
        )
        DriverVerification.objects.create(
            user=user,
            status=DriverVerification.Status.APPROVED,
            source=DriverVerification.Source.SEED,
            full_name_on_document=user.full_name or user.get_full_name(),
            license_number_normalized=normalize_license(license_data["license_number"]),
            personal_number=make_personal_number(license_data["date_of_birth"], spec.get("sex", "m")),
            consent_version=settings.CONSENT_VERSION,
            consent_given_at=now,
            biometric_consent_at=now,
            liveness_passed_at=now,
            submitted_at=now,
            reviewed_at=now,
            **license_data,
        )
        sync_user_status(user)
    return users


LETTERS = "ABEHKMOPCTX"


def demo_persona(user):
    """Демо-режим: «запись в реестре ГАИ» на ФИО пользователя с согласованными данными.

    Так на защите любой новый аккаунт можно провести через проверку без настоящих прав.
    Документы и кадры при этом помечаются как демо, а в боевом режиме
    (KYC_DEMO_MODE=False) эта функция недоступна.
    """
    tag = f"demo:{user.pk}"
    record = LicenseRegistryRecord.objects.filter(note=tag).first()
    if record is None:
        rng = random.Random(user.pk * 7919)
        birth = date(rng.randint(1975, 2001), rng.randint(1, 12), rng.randint(1, 28))
        issued = date(rng.randint(max(birth.year + 18, 2018), 2025), rng.randint(1, 12), rng.randint(1, 28))
        category_b = min(add_years(birth, 18 + rng.randint(0, 4)), issued)
        term = 20 if issued >= LONG_LICENSE_SINCE else 10
        while True:
            number = f"{rng.randint(1, 7)}{rng.choice(LETTERS)}{rng.choice(LETTERS)}{rng.randint(0, 999999):06d}"
            if not LicenseRegistryRecord.objects.filter(number_normalized=number).exists():
                break
        full_name = " ".join(part for part in (user.last_name, user.first_name, user.patronymic) if part)
        record = LicenseRegistryRecord.objects.create(
            number_normalized=number,
            full_name=full_name or user.username,
            date_of_birth=birth,
            issued_on=issued,
            expires_on=add_years(issued, term),
            category_b_since=category_b,
            note=tag,
        )
    number = record.number_normalized
    return {
        "document_type": "passport_by",
        "full_name_on_document": record.full_name,
        "date_of_birth": record.date_of_birth,
        "personal_number": make_personal_number(record.date_of_birth, serial=user.pk % 1000),
        "license_country": "BY",
        "license_number": f"{number[:3]} {number[3:]}",
        "license_issued_on": record.issued_on,
        "license_expires_on": record.expires_on,
        "category_b_since": record.category_b_since,
    }

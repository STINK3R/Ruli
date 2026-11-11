"""«Рули ID»: автопроверки, решения модератора и допуск водителя к классам машин."""

import re
import statistics
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import kyc
from .models import (
    ClassRequirement,
    DriverVerification,
    LivenessFrame,
    User,
    VerificationDocument,
    VerificationEvent,
    VerificationStatus,
)

V = DriverVerification.Status
REQUIRED_KINDS = [kind.value for kind in VerificationDocument.Kind]
CLASS_LABELS = {"economy": "Эконом", "comfort": "Комфорт", "business": "Бизнес", "premium": "Премиум"}
LEVELS = {0: "Гость", 1: "На проверке", 2: "Проверенный водитель", 3: "Допуск Плюс"}
CYRILLIC_TWINS = str.maketrans("АВЕКМНОРСТУХІ", "ABEKMHOPCTYXI")
BY_LICENSE_RE = re.compile(r"^\d[ABEIKMHOPCTX]{2}\d{6}$")
# С 23.03.2024 ВУ в РБ выдаются на 20 лет (Указ № 55), раньше — на 10.
LONG_LICENSE_SINCE = date(2024, 3, 23)

REASON_TEXTS = {
    "blurry_photo": "Фото размыто — переснимите при хорошем освещении.",
    "glare": "На документе блик — снимите без вспышки, под небольшим углом.",
    "cropped": "Документ попал в кадр не целиком.",
    "selfie_mismatch": "Лицо на селфи не совпадает с фото в документе.",
    "data_mismatch": "Данные в анкете не совпадают с документами.",
    "not_original": "Нужны фото оригиналов — не копий и не экрана.",
    "no_category_b": "В удостоверении нет категории B.",
    "underage": "Сервис доступен с 18 лет.",
    "license_expired": "Срок действия прав истёк — загрузите действующее удостоверение.",
    "duplicate_license": "Эти права уже подтверждены на другом аккаунте — напишите в поддержку.",
    "suspected_fraud": "Заявка отклонена службой безопасности.",
    "registry_mismatch": "Данные не совпадают с реестром ГАИ.",
    "liveness_failed": "Проверка «живости» не пройдена — пройдите её заново перед камерой.",
    "other": "Подробности — в комментарии модератора.",
}

# Сколько баллов риска даёт предупреждение. Больше 50 — модератор смотрит особенно внимательно.
RISK_WEIGHTS = {
    "duplicate_image": 40,
    "demo_documents": 30,
    "name_mismatch": 25,
    "many_attempts": 20,
    "foreign_license": 15,
    "registry_category_date": 15,
    "license_number_format": 10,
    "license_validity_term": 10,
    "category_b_age": 10,
    "selfie_freshness": 10,
    "expires_soon": 5,
}
BY_DOCUMENTS = ("passport_by", "id_card_by")


def today():
    return timezone.localdate()


def plural(number, forms):
    """plural(2, ("поездка", "поездки", "поездок")) → «2 поездки»."""
    n = abs(number) % 100
    if 11 <= n <= 14:
        form = forms[2]
    else:
        form = {1: forms[0], 2: forms[1], 3: forms[1], 4: forms[1]}.get(n % 10, forms[2])
    return f"{number} {form}"


TRIPS = ("поездка", "поездки", "поездок")


def normalize_license(number):
    value = (number or "").upper().translate(CYRILLIC_TWINS)
    return re.sub(r"[\s\-]", "", value)


def full_years(start, on):
    if not start:
        return None
    return on.year - start.year - ((on.month, on.day) < (start.month, start.day))


def add_years(day, years):
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 февраля в невисокосный год
        return day.replace(year=day.year + years, day=28)


def log(verification, action, actor=None, **meta):
    VerificationEvent.objects.create(verification=verification, action=action, actor=actor, meta=meta)


def delete_documents(documents):
    """Удаляет фото документов. Возвращает число удалённых.

    Файл убирает обработчик post_delete после коммита: при откате строка вернётся вместе с файлом.
    """
    count = 0
    for document in documents:
        document.delete()
        count += 1
    return count


# ---------- Автопроверки ----------

def run_auto_checks(verification):
    on = today()
    checks = []

    def add(code, level, message, step):
        checks.append({"code": code, "level": level, "message": message, "step": step})

    documents = list(verification.documents.all())
    kinds = {doc.kind for doc in documents}
    v = verification

    if not v.user.phone_verified:
        add("phone", "fail", "Подтвердите номер телефона кодом из SMS.", "phone")
    if any(kind not in kinds for kind in REQUIRED_KINDS):
        add("files_complete", "fail", "Снимите все 4 документа.", "documents")
    if any(doc.needs_reshoot for doc in documents):
        add("reshoot_pending", "fail", "Переснимите фото, отмеченные модератором.", "documents")
    liveness_fresh = bool(
        v.liveness_passed_at
        and timezone.now() - v.liveness_passed_at <= timedelta(hours=settings.LIVENESS_VALID_HOURS)
    )
    if not liveness_fresh:
        add("liveness", "fail", "Пройдите проверку «живости» — 15 секунд перед камерой.", "liveness")

    # Личный номер есть в паспорте и ID-карте РБ: в нём зашиты дата рождения и контрольная цифра.
    if v.document_type in BY_DOCUMENTS:
        if not v.personal_number:
            add("personal_number", "fail", "Укажите личный номер из паспорта или ID-карты.", "data")
        else:
            try:
                birth, _sex, citizenship = kyc.parse_personal_number(v.personal_number)
            except ValueError as error:
                add("personal_number", "fail", str(error), "data")
            else:
                if v.date_of_birth and birth != v.date_of_birth:
                    add("personal_number_birth", "fail",
                        "Дата рождения не совпадает с зашитой в личный номер.", "data")
                if citizenship != "PB":
                    add("personal_number_citizen", "warn",
                        "Личный номер не гражданина РБ — проверьте вид документа.", "data")

    fields = (v.full_name_on_document, v.date_of_birth, v.license_number,
              v.license_issued_on, v.license_expires_on, v.category_b_since)
    if not all(fields):
        add("fields_complete", "fail", "Заполните все поля анкеты.", "data")
    else:
        if full_years(v.date_of_birth, on) < 18:
            add("age_min", "fail", "Сервис доступен с 18 лет.", "data")
        if v.license_issued_on > on:
            add("license_dates", "fail", "Дата выдачи прав не может быть в будущем.", "data")
        if v.license_expires_on <= v.license_issued_on:
            add("license_dates", "fail", "Срок действия должен быть позже даты выдачи.", "data")
        if v.license_expires_on <= on:
            add("license_not_expired", "fail", "Срок действия прав истёк — нужно действующее удостоверение.", "data")
        elif v.license_expires_on <= on + timedelta(days=30):
            add("expires_soon", "warn", "Права истекают в ближайшие 30 дней.", "data")
        if v.category_b_since > v.license_issued_on:
            add("license_dates", "fail", "Категория B не может быть открыта позже выдачи удостоверения.", "data")
        if v.category_b_since < add_years(v.date_of_birth, 16):
            add("license_dates", "fail", "Категория B не может быть открыта раньше 16 лет.", "data")
        elif v.category_b_since < add_years(v.date_of_birth, 18):
            add("category_b_age", "warn", "Категория B открыта до 18 лет — нетипично для РБ.", "data")

        normalized = normalize_license(v.license_number)
        if v.license_country == "BY":
            if not BY_LICENSE_RE.match(normalized):
                add("license_number_format", "warn", "Номер не похож на белорусский формат «5AB 123456».", "data")
            term = 20 if v.license_issued_on >= LONG_LICENSE_SINCE else 10
            expected = add_years(v.license_issued_on, term)
            if abs((v.license_expires_on - expected).days) > 31:
                add("license_validity_term", "warn", f"Для прав РБ срок обычно {term} лет — проверьте даты.", "data")

        taken = (
            User.objects.filter(license_key=normalized).exclude(pk=v.user_id).exists()
            or DriverVerification.objects.filter(
                license_number_normalized=normalized, status__in=[V.PENDING, V.NEEDS_FIX, V.APPROVED]
            ).exclude(user_id=v.user_id).exists()
        )
        if taken:
            add("duplicate_license", "fail", REASON_TEXTS["duplicate_license"], "data")

        for code, level, message in kyc.registry_checks(v, normalized):
            add(code, level, message, "data")

        doc_name = re.sub(r"\s+", " ", v.full_name_on_document.lower().replace("ё", "е")).strip()
        user = v.user
        for part in (user.last_name, user.first_name):
            if part and part.lower().replace("ё", "е") not in doc_name:
                add("name_mismatch", "warn", "ФИО в документе отличается от имени в профиле.", "data")
                break

    if not v.consent_given_at or not v.biometric_consent_at:
        add("consents", "fail", "Нужны оба согласия на обработку данных.", "consent")

    hashes = [doc.sha256 for doc in documents]
    if hashes and VerificationDocument.objects.filter(sha256__in=hashes).exclude(
        verification__user_id=v.user_id
    ).exists():
        add("duplicate_image", "warn", "Такое же фото уже загружал другой пользователь.", "documents")

    # Свежесть подтверждает проверка «живости»; без неё смотрим на дату съёмки селфи.
    selfie = next((doc for doc in documents if doc.kind == VerificationDocument.Kind.SELFIE), None)
    stale_selfie = not selfie or not selfie.captured_at or timezone.now() - selfie.captured_at > timedelta(hours=24)
    if selfie and stale_selfie and not liveness_fresh:
        add("selfie_freshness", "warn", "Селфи без даты съёмки или старше суток.", "documents")

    demo_liveness = v.liveness_checks.filter(status="passed", is_demo=True).exists()
    if any(doc.is_demo for doc in documents) or demo_liveness:
        add("demo_documents", "warn", "Демо-изображения, нарисованные приложением, — не настоящие документы.",
            "documents")

    recent_rejections = v.user.verifications.filter(
        status=V.REJECTED, reviewed_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    if recent_rejections >= 3:
        add("many_attempts", "warn", "Три и больше отказов за 30 дней.", "data")
    return checks


# ---------- Статус пользователя ----------

def sync_user_status(user):
    """Статус пользователя = действующее одобрение или последняя заявка.

    Пока проверяется обновление документов, прежнее одобрение продолжает действовать.
    """
    if user.verification_status == VerificationStatus.BLOCKED:
        return user

    approved = user.verifications.filter(status=V.APPROVED).order_by("-reviewed_at", "-id").first()
    latest = user.verifications.exclude(status=V.SUPERSEDED).order_by("-created_at", "-id").first()

    fields = ["verification_status", "license_key"]
    if approved:
        expired = approved.license_expires_on and approved.license_expires_on < today()
        user.verification_status = VerificationStatus.EXPIRED if expired else VerificationStatus.APPROVED
        user.license_key = approved.license_number_normalized or None
        user.date_of_birth = approved.date_of_birth or user.date_of_birth
        user.driver_license_number = approved.license_number or user.driver_license_number
        user.driver_license_issued = approved.license_issued_on or user.driver_license_issued
        user.driving_since = approved.experience_since or user.driving_since
        user.license_expires_on = approved.license_expires_on
        fields += [
            "date_of_birth", "driver_license_number", "driver_license_issued",
            "driving_since", "license_expires_on",
        ]
    elif latest:
        user.verification_status = {
            V.DRAFT: VerificationStatus.DRAFT,
            V.PENDING: VerificationStatus.PENDING,
            V.NEEDS_FIX: VerificationStatus.NEEDS_FIX,
            V.REJECTED: VerificationStatus.REJECTED,
        }.get(latest.status, VerificationStatus.NONE)
        in_review = latest.status in (V.PENDING, V.NEEDS_FIX)
        user.license_key = latest.license_number_normalized if in_review else None
    else:
        user.verification_status = VerificationStatus.NONE
        user.license_key = None

    try:
        with transaction.atomic():
            user.save(update_fields=fields)
    except IntegrityError:
        raise ValidationError({"detail": REASON_TEXTS["duplicate_license"], "code": "duplicate_license"})
    return user


# ---------- Переходы заявки ----------

def _locked(verification):
    return DriverVerification.objects.select_for_update().select_related("user").get(pk=verification.pk)


@transaction.atomic
def submit(verification):
    v = _locked(verification)
    if v.status not in (V.DRAFT, V.NEEDS_FIX):
        raise ValidationError({"detail": "Заявка уже на проверке.", "code": "already_submitted"})

    v.license_number_normalized = normalize_license(v.license_number)
    v.personal_number = kyc.normalize_personal_number(v.personal_number)
    checks = run_auto_checks(v)
    v.auto_checks = checks
    failed = [check for check in checks if check["level"] == "fail"]
    if failed:
        v.save(update_fields=["auto_checks", "license_number_normalized", "personal_number", "updated_at"])
        raise ValidationError({"detail": failed[0]["message"], "code": "checks_failed", "checks": failed})

    v.status = V.PENDING
    v.submitted_at = timezone.now()
    warnings = [check for check in checks if check["level"] == "warn"]
    v.warnings_count = len(warnings)
    v.risk_score = min(100, sum(RISK_WEIGHTS.get(check["code"], 10) for check in warnings))
    v.save()
    v.documents.update(needs_reshoot=False)
    sync_user_status(v.user)
    log(v, VerificationEvent.Action.SUBMITTED, v.user, warnings=v.warnings_count)
    return v


@transaction.atomic
def approve(verification, reviewer):
    v = _locked(verification)
    if v.status != V.PENDING:
        raise ValidationError("Одобрить можно только заявку на проверке.")
    # Реестр мог измениться, пока заявка ждала модератора: лишённого водителя не одобрить.
    blocking = [msg for _code, level, msg in kyc.registry_checks(v, v.license_number_normalized) if level == "fail"]
    if blocking:
        raise ValidationError(blocking[0])
    v.user.verifications.filter(status=V.APPROVED).exclude(pk=v.pk).update(status=V.SUPERSEDED)
    v.status = V.APPROVED
    v.reviewer = reviewer
    v.reviewed_at = timezone.now()
    v.rejection_reason = ""
    v.save()
    sync_user_status(v.user)
    log(v, VerificationEvent.Action.APPROVED, reviewer)
    from rewards.services import on_verified

    on_verified(v.user)
    return v


@transaction.atomic
def request_fix(verification, reviewer, reason, kinds=None, comment=""):
    v = _locked(verification)
    if v.status != V.PENDING:
        raise ValidationError("Отправить на пересъёмку можно только заявку на проверке.")
    documents = v.documents.all()
    if kinds:
        documents = documents.filter(kind__in=kinds)
    documents.update(needs_reshoot=True)
    v.status = V.NEEDS_FIX
    v.rejection_reason = reason
    v.reviewer_comment = comment or v.reviewer_comment
    v.reviewer = reviewer
    v.reviewed_at = timezone.now()
    v.save()
    sync_user_status(v.user)
    log(v, VerificationEvent.Action.NEEDS_FIX, reviewer, reason=reason, kinds=list(kinds or []))
    return v


@transaction.atomic
def reject(verification, reviewer, reason, comment=""):
    v = _locked(verification)
    if v.status not in (V.PENDING, V.NEEDS_FIX):
        raise ValidationError("Отклонить можно только заявку на проверке.")
    v.status = V.REJECTED
    v.rejection_reason = reason
    v.reviewer_comment = comment or v.reviewer_comment
    v.reviewer = reviewer
    v.reviewed_at = timezone.now()
    v.save()
    sync_user_status(v.user)
    log(v, VerificationEvent.Action.REJECTED, reviewer, reason=reason)
    return v


@transaction.atomic
def revoke(verification, reviewer, reason):
    v = _locked(verification)
    if v.status != V.APPROVED:
        raise ValidationError("Отозвать можно только одобренную заявку.")
    v.status = V.REVOKED
    v.rejection_reason = reason
    v.reviewer = reviewer
    v.reviewed_at = timezone.now()
    v.save()
    sync_user_status(v.user)
    log(v, VerificationEvent.Action.REVOKED, reviewer, reason=reason)
    return v


@transaction.atomic
def withdraw_consent(user):
    """Отзыв согласия (ст. 10, 13 Закона № 99-З): файлы удаляются сразу, одобрение отзывается."""
    now = timezone.now()
    # Кадры лица — биометрия: при отзыве согласия удаляются все, включая снятые перед поездками.
    delete_documents(LivenessFrame.objects.filter(check_run__user=user))
    for v in user.verifications.select_for_update():
        delete_documents(v.documents.all())
        v.liveness_passed_at = None
        if v.status in (V.DRAFT, V.PENDING, V.NEEDS_FIX, V.APPROVED):
            v.status = V.REVOKED
        v.files_purged_at = now
        v.save(update_fields=["status", "files_purged_at", "liveness_passed_at", "updated_at"])
        log(v, VerificationEvent.Action.CONSENT_WITHDRAWN, user)
    # Отзыв согласия не снимает блокировку службы безопасности.
    if user.verification_status != VerificationStatus.BLOCKED:
        user.verification_status = VerificationStatus.NONE
    user.license_key = None
    user.save(update_fields=["verification_status", "license_key"])


def ensure_not_blocked(user):
    if user.verification_status == VerificationStatus.BLOCKED:
        raise PermissionDenied({"detail": NEXT_STEPS[VerificationStatus.BLOCKED], "code": "blocked"})


def expected_wait_minutes():
    reviewed = DriverVerification.objects.filter(
        submitted_at__isnull=False, reviewed_at__isnull=False, source=DriverVerification.Source.APP
    ).order_by("-reviewed_at")[:20]
    durations = [
        max(1, round((v.reviewed_at - v.submitted_at).total_seconds() / 60)) for v in reviewed
    ]
    return round(statistics.median(durations)) if durations else 10


# ---------- Допуск к классам ----------

def clean_trip_count(user, days=180):
    from rentals.models import Rental

    since = timezone.now() - timedelta(days=days)
    rentals = Rental.objects.filter(
        user=user, status=Rental.Status.COMPLETED, finished_at__gte=since
    )
    try:
        from inspections.models import Damage
    except ImportError:  # приложение осмотров не подключено
        return rentals.count()
    blamed = Damage.objects.filter(status=Damage.Status.CONFIRMED).values("responsible_rental_id")
    return rentals.exclude(pk__in=blamed).count()


def _effective_status(user, on):
    status = user.verification_status
    if status == VerificationStatus.APPROVED and user.license_expires_on and user.license_expires_on < on:
        return VerificationStatus.EXPIRED
    # Лишение прав после одобрения: реестр проверяется при каждом расчёте допуска.
    if status == VerificationStatus.APPROVED and kyc.registry_blocks(user):
        return VerificationStatus.LICENSE_INVALID
    return status


NEXT_STEPS = {
    VerificationStatus.NONE: "Подтвердите права — это займёт 5 минут.",
    VerificationStatus.DRAFT: "Закончите анкету и загрузите фото документов.",
    VerificationStatus.PENDING: "Документы на проверке у модератора.",
    VerificationStatus.NEEDS_FIX: "Переснимите отмеченные фото и отправьте снова.",
    VerificationStatus.REJECTED: "Заявка отклонена — исправьте данные и отправьте новую.",
    VerificationStatus.EXPIRED: "Срок действия прав истёк — загрузите новое удостоверение.",
    VerificationStatus.LICENSE_INVALID: "По данным ГАИ права сейчас недействительны — поездки закрыты.",
    VerificationStatus.BLOCKED: "Аккаунт заблокирован — обратитесь в поддержку.",
}


def access_policy(user, on=None):
    """Что водителю доступно сейчас и когда откроется остальное."""
    on = on or today()
    status = _effective_status(user, on)
    approved = status == VerificationStatus.APPROVED
    trips = clean_trip_count(user) if approved else 0
    plus_target = settings.PLUS_LEVEL_TRIPS

    if approved:
        level = 3 if trips >= plus_target else 2
    elif status in (VerificationStatus.PENDING, VerificationStatus.NEEDS_FIX):
        level = 1
    else:
        level = 0

    # Номер сменили после одобрения — поездки снова откроет только код из SMS.
    phone_ok = user.phone_verified
    if approved and not phone_ok:
        next_step = "Подтвердите новый номер телефона кодом из SMS."
    elif approved:
        next_step = (
            "Максимальный уровень: +5 минут бесплатной брони."
            if level == 3
            else f"Ещё {plural(plus_target - trips, TRIPS)} без замечаний до «Допуска Плюс»."
        )
    else:
        next_step = NEXT_STEPS.get(status, NEXT_STEPS[VerificationStatus.NONE])

    age = full_years(user.date_of_birth, on)
    experience = full_years(user.driving_since, on)
    requirements = {req.car_class: req for req in ClassRequirement.objects.all()}

    classes = {}
    for car_class, label in CLASS_LABELS.items():
        req = requirements.get(car_class)
        reasons, unlock_on, hint = [], None, ""
        if not approved:
            reasons.append("verification")
            hint = next_step
        elif not phone_ok:
            reasons.append("phone")
            hint = next_step
        elif req:
            if age is None or age < req.min_age:
                reasons.append("age")
            if experience is None or experience < req.min_experience_years:
                reasons.append("experience")
            if trips < req.min_completed_rentals:
                reasons.append("trips")

            dates = []
            if "age" in reasons and user.date_of_birth:
                dates.append(add_years(user.date_of_birth, req.min_age))
            if "experience" in reasons and user.driving_since:
                dates.append(add_years(user.driving_since, req.min_experience_years))
            if dates and "trips" not in reasons:
                unlock_on = max(dates)
                hint = f"{label} откроется {unlock_on:%d.%m.%Y}."
            elif "trips" in reasons:
                missing = req.min_completed_rentals - trips
                hint = f"Нужно ещё {plural(missing, TRIPS)} без замечаний."
                if dates:
                    hint += f" По возрасту и стажу — с {max(dates):%d.%m.%Y}."
        classes[car_class] = {
            "label": label,
            "allowed": not reasons,
            "reasons": reasons,
            "unlock_on": unlock_on,
            "hint": hint,
            "requirement": {
                "min_age": req.min_age,
                "min_experience_years": req.min_experience_years,
                "min_completed_rentals": req.min_completed_rentals,
                "note": req.note,
            }
            if req
            else None,
        }

    expires = user.license_expires_on
    return {
        "status": status,
        "status_display": VerificationStatus(status).label,
        "level": level,
        "level_display": LEVELS[level],
        "clean_trips": trips,
        "plus_target": plus_target,
        "next_step": next_step,
        "license_expires_on": expires,
        "license_expires_soon": bool(expires and on <= expires <= on + timedelta(days=30)),
        "novice": approved and experience is not None and experience < 2,
        "age": age,
        "experience_years": experience,
        "classes": classes,
    }


DENIAL_CODES = {
    VerificationStatus.PENDING: "verification_pending",
    VerificationStatus.NEEDS_FIX: "verification_pending",
    VerificationStatus.EXPIRED: "license_expired",
    VerificationStatus.LICENSE_INVALID: "license_invalid",
    VerificationStatus.BLOCKED: "blocked",
}


def check_can_rent(user, car, policy=None):
    """Бросает 403 с понятной причиной, если водителю нельзя брать этот класс."""
    policy = policy or access_policy(user)
    entry = policy["classes"][car.car_class]
    if entry["allowed"]:
        return policy
    if "verification" in entry["reasons"]:
        code = DENIAL_CODES.get(policy["status"], "verification_required")
    elif "phone" in entry["reasons"]:
        code = "phone_required"
    else:
        code = "class_locked"
    detail = {"detail": entry["hint"] or policy["next_step"], "code": code, "reasons": entry["reasons"]}
    # Без ключа, если даты нет: DRF превратил бы None в строку «None».
    if entry["unlock_on"]:
        detail["unlock_on"] = entry["unlock_on"].isoformat()
    raise PermissionDenied(detail)

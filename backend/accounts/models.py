from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .storage import document_upload_path, private_document_storage


class VerificationStatus(models.TextChoices):
    """Статус водителя целиком (копия решения по последней заявке)."""

    NONE = "none", "Не подтверждён"
    DRAFT = "draft", "Заполняет данные"
    PENDING = "pending", "На проверке"
    NEEDS_FIX = "needs_fix", "Нужно переснять фото"
    APPROVED = "approved", "Права подтверждены"
    REJECTED = "rejected", "Отклонено"
    EXPIRED = "expired", "Права истекли"
    LICENSE_INVALID = "license_invalid", "Права недействительны по реестру"
    BLOCKED = "blocked", "Заблокирован"


class User(AbstractUser):
    """Пользователь каршеринга.

    Роль определяется встроенным флагом is_staff: клиент — обычный пользователь,
    администратор — сотрудник с доступом к панели управления. Допуск к поездкам
    даёт только одобренная заявка «Рули ID» (DriverVerification).
    """

    email = models.EmailField("Email", unique=True)
    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    phone_number = models.CharField(
        "Телефон", max_length=20, unique=True, null=True, blank=True
    )
    # Номер подтверждён кодом из SMS: без этого заявку «Рули ID» не отправить.
    phone_verified_at = models.DateTimeField("Телефон подтверждён", null=True, blank=True)
    date_of_birth = models.DateField("Дата рождения", null=True, blank=True)
    driver_license_number = models.CharField(
        "Номер водительского удостоверения", max_length=20, blank=True
    )
    driver_license_issued = models.DateField("Дата выдачи ВУ", null=True, blank=True)
    driving_since = models.DateField(
        "Стаж с", null=True, blank=True, help_text="Дата открытия категории B"
    )
    license_expires_on = models.DateField("ВУ действительно до", null=True, blank=True)
    verification_status = models.CharField(
        "Статус Рули ID",
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.NONE,
        db_index=True,
    )
    # Нормализованный номер ВУ из действующей заявки. UNIQUE не даёт подтвердить
    # одни и те же права на двух аккаунтах даже при одновременных запросах.
    license_key = models.CharField(max_length=20, null=True, blank=True, unique=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def save(self, *args, **kwargs):
        # Пустая строка нарушила бы unique-ограничение при нескольких
        # пользователях без телефона, NULL — нет.
        if not self.phone_number:
            self.phone_number = None
        if not self.license_key:
            self.license_key = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.patronymic]
        return " ".join(p for p in parts if p)

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.APPROVED

    @property
    def phone_verified(self):
        return bool(self.phone_number and self.phone_verified_at)


class PhoneCode(models.Model):
    """Одноразовый код из SMS. Хранится только хэш — код не прочитать даже из базы."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="phone_codes"
    )
    phone = models.CharField("Телефон", max_length=20)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField("Попыток ввода", default=0)
    created_at = models.DateTimeField("Отправлен", auto_now_add=True)
    expires_at = models.DateTimeField("Действует до")
    used_at = models.DateTimeField("Использован", null=True, blank=True)

    class Meta:
        verbose_name = "Код из SMS"
        verbose_name_plural = "Коды из SMS"
        ordering = ("-created_at",)


class LicenseRegistryRecord(models.Model):
    """Имитация реестра водительских удостоверений ГАИ МВД РБ.

    В настоящем сервисе это запрос к ведомственной системе; здесь — справочник,
    который сотрудник ведёт в админке. По нему ловятся выдуманные номера,
    чужие права и лишение права управления уже после одобрения.
    """

    class Status(models.TextChoices):
        VALID = "valid", "Действительно"
        SUSPENDED = "suspended", "Лишение права управления"
        INVALID = "invalid", "Недействительно (утеряно, заменено)"

    number_normalized = models.CharField("Номер ВУ", max_length=20, unique=True)
    full_name = models.CharField("ФИО", max_length=255)
    date_of_birth = models.DateField("Дата рождения")
    issued_on = models.DateField("Дата выдачи")
    expires_on = models.DateField("Действительно до")
    categories = models.CharField("Категории", max_length=40, default="B")
    category_b_since = models.DateField("Категория B открыта", null=True, blank=True)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.VALID, db_index=True
    )
    suspended_until = models.DateField("Лишение до", null=True, blank=True)
    note = models.CharField("Примечание", max_length=200, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Запись реестра ВУ (имитация ГАИ)"
        verbose_name_plural = "Реестр ВУ (имитация ГАИ)"
        ordering = ("number_normalized",)

    def __str__(self):
        return f"{self.number_normalized} — {self.full_name} — {self.get_status_display()}"


class ClassRequirement(models.Model):
    """Требования к водителю по классу автомобиля — меняются в админке без кода."""

    car_class = models.CharField("Класс", max_length=20, unique=True)
    min_age = models.PositiveSmallIntegerField("Возраст от, лет")
    min_experience_years = models.PositiveSmallIntegerField("Стаж от, лет")
    min_completed_rentals = models.PositiveSmallIntegerField(
        "Поездок без замечаний", default=0
    )
    note = models.CharField("Пояснение для клиента", max_length=200, blank=True)

    class Meta:
        verbose_name = "Требования класса"
        verbose_name_plural = "Требования по классам"
        ordering = ("min_age", "min_experience_years")

    def __str__(self):
        return f"{self.car_class}: {self.min_age}+ лет, стаж {self.min_experience_years}+"


class DriverVerification(models.Model):
    """Заявка на подтверждение водителя. Одна строка — одна попытка, история хранится."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PENDING = "pending", "На проверке"
        NEEDS_FIX = "needs_fix", "Нужно переснять"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        SUPERSEDED = "superseded", "Заменена новой"
        REVOKED = "revoked", "Отозвана"

    class Source(models.TextChoices):
        APP = "app", "Приложение"
        LEGACY = "legacy", "Перенос из старой системы"
        SEED = "seed", "Демо-данные"

    class DocumentType(models.TextChoices):
        PASSPORT_BY = "passport_by", "Паспорт РБ"
        ID_CARD_BY = "id_card_by", "ID-карта РБ"
        FOREIGN = "foreign_passport", "Иностранный паспорт"

    class Reason(models.TextChoices):
        BLURRY_PHOTO = "blurry_photo", "Фото размыто"
        GLARE = "glare", "Блик на документе"
        CROPPED = "cropped", "Документ обрезан"
        SELFIE_MISMATCH = "selfie_mismatch", "Лицо на селфи не совпадает"
        DATA_MISMATCH = "data_mismatch", "Данные не совпадают с фото"
        NOT_ORIGINAL = "not_original", "Не оригинал документа"
        NO_CATEGORY_B = "no_category_b", "Нет категории B"
        UNDERAGE = "underage", "Возраст меньше 18 лет"
        LICENSE_EXPIRED = "license_expired", "Срок действия прав истёк"
        DUPLICATE_LICENSE = "duplicate_license", "Права уже подтверждены на другом аккаунте"
        SUSPECTED_FRAUD = "suspected_fraud", "Подозрение на мошенничество"
        OTHER = "other", "Другое"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="verifications",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    source = models.CharField("Источник", max_length=10, choices=Source.choices, default=Source.APP)
    document_type = models.CharField(
        "Документ личности",
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.PASSPORT_BY,
    )
    full_name_on_document = models.CharField("ФИО как в документе", max_length=255, blank=True)
    date_of_birth = models.DateField("Дата рождения", null=True, blank=True)
    license_country = models.CharField("Страна выдачи ВУ", max_length=2, default="BY")
    license_number = models.CharField("Номер ВУ", max_length=20, blank=True)
    license_number_normalized = models.CharField(max_length=20, blank=True, db_index=True)
    license_issued_on = models.DateField("Дата выдачи ВУ (4a)", null=True, blank=True)
    license_expires_on = models.DateField("Действительно до (4b)", null=True, blank=True)
    category_b_since = models.DateField(
        "Категория B открыта", null=True, blank=True, help_text="Оборот ВУ, столбец 10 — от неё считается стаж"
    )
    personal_number = models.CharField(
        "Личный номер",
        max_length=14,
        blank=True,
        help_text="Идентификационный номер из паспорта или ID-карты РБ, 14 знаков",
    )
    risk_score = models.PositiveSmallIntegerField("Риск, баллов", default=0)
    liveness_passed_at = models.DateTimeField("Проверка «живости» пройдена", null=True, blank=True)
    experience_since_override = models.DateField(
        "Стаж с (поправка модератора)",
        null=True,
        blank=True,
        help_text="Например, если был перерыв из-за лишения прав",
    )
    auto_checks = models.JSONField("Автопроверки", default=list, blank=True)
    warnings_count = models.PositiveSmallIntegerField("Предупреждений", default=0)
    rejection_reason = models.CharField(
        "Причина решения", max_length=30, choices=Reason.choices, blank=True
    )
    reviewer_comment = models.TextField("Комментарий для клиента", blank=True)
    internal_note = models.TextField("Заметка для сотрудников", blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Модератор",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verifications",
    )
    consent_version = models.CharField("Версия согласия", max_length=20, blank=True)
    consent_given_at = models.DateTimeField("Согласие на обработку данных", null=True, blank=True)
    biometric_consent_at = models.DateTimeField("Согласие на обработку фото лица", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Изменена", auto_now=True)
    submitted_at = models.DateTimeField("Отправлена", null=True, blank=True)
    reviewed_at = models.DateTimeField("Решение принято", null=True, blank=True)
    files_purged_at = models.DateTimeField("Файлы удалены", null=True, blank=True)

    class Meta:
        verbose_name = "Заявка Рули ID"
        verbose_name_plural = "Заявки Рули ID"
        ordering = ("submitted_at", "id")
        indexes = [models.Index(fields=["status", "submitted_at"])]

    def __str__(self):
        return f"Заявка #{self.pk} — {self.user} — {self.get_status_display()}"

    @property
    def experience_since(self):
        return self.experience_since_override or self.category_b_since or self.license_issued_on


class VerificationDocument(models.Model):
    class Kind(models.TextChoices):
        LICENSE_FRONT = "license_front", "ВУ — лицевая сторона"
        LICENSE_BACK = "license_back", "ВУ — оборот с категориями"
        PASSPORT_MAIN = "passport_main", "Паспорт — разворот с фото"
        SELFIE = "selfie_with_license", "Селфи с ВУ в руке"

    verification = models.ForeignKey(
        DriverVerification,
        verbose_name="Заявка",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    kind = models.CharField("Документ", max_length=30, choices=Kind.choices)
    file = models.ImageField(
        "Файл", storage=private_document_storage, upload_to=document_upload_path
    )
    sha256 = models.CharField("SHA-256 оригинала", max_length=64, db_index=True)
    is_demo = models.BooleanField(
        "Демо-изображение",
        default=False,
        help_text="Нарисовано приложением для защиты, не настоящий документ",
    )
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveIntegerField(default=0)
    captured_at = models.DateTimeField("Снято (EXIF)", null=True, blank=True)
    needs_reshoot = models.BooleanField("Нужно переснять", default=False)
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        constraints = [
            models.UniqueConstraint(fields=["verification", "kind"], name="one_document_per_kind")
        ]

    def __str__(self):
        return f"{self.get_kind_display()} (заявка #{self.verification_id})"


class VerificationEvent(models.Model):
    """Журнал аудита: кто и что делал с заявкой, включая каждый просмотр фото сотрудником."""

    class Action(models.TextChoices):
        CREATED = "created", "Создана"
        DOCUMENT_UPLOADED = "document_uploaded", "Загружен документ"
        SUBMITTED = "submitted", "Отправлена"
        APPROVED = "approved", "Одобрена"
        NEEDS_FIX = "needs_fix", "Отправлена на пересъёмку"
        REJECTED = "rejected", "Отклонена"
        REVOKED = "revoked", "Одобрение отозвано"
        DOCUMENT_VIEWED = "document_viewed", "Сотрудник открыл документ"
        CONSENT_WITHDRAWN = "consent_withdrawn", "Согласие отозвано, файлы удалены"
        FILES_PURGED = "files_purged", "Файлы удалены по сроку хранения"
        LIVENESS_PASSED = "liveness_passed", "Проверка «живости» пройдена"
        LIVENESS_FAILED = "liveness_failed", "Проверка «живости» не пройдена"

    verification = models.ForeignKey(
        DriverVerification, on_delete=models.CASCADE, related_name="events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField("Действие", max_length=30, choices=Action.choices)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        verbose_name = "Событие Рули ID"
        verbose_name_plural = "Журнал Рули ID"
        ordering = ("-created_at",)


class LivenessCheck(models.Model):
    """Проверка «живости»: случайная последовательность движений перед камерой.

    Движения выбирает сервер, на съёмку — две минуты: заранее подготовленное
    фото или видео под случайный набор не подходит. Та же проверка, только
    короче, — перед каждой поездкой: за руль садится владелец аккаунта.
    """

    class Purpose(models.TextChoices):
        KYC = "kyc", "Рули ID"
        TRIP = "trip", "Перед поездкой"

    class Status(models.TextChoices):
        PENDING = "pending", "Ждёт кадров"
        PASSED = "passed", "Пройдена"
        FAILED = "failed", "Не пройдена"
        EXPIRED = "expired", "Время вышло"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="liveness_checks",
    )
    verification = models.ForeignKey(
        DriverVerification,
        verbose_name="Заявка",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="liveness_checks",
    )
    purpose = models.CharField("Назначение", max_length=10, choices=Purpose.choices, default=Purpose.KYC)
    steps = models.JSONField("Движения", default=list)
    status = models.CharField(
        "Статус", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    motion_score = models.FloatField("Движение в кадре", null=True, blank=True)
    failure_reason = models.CharField("Причина отказа", max_length=200, blank=True)
    is_demo = models.BooleanField("Демо-кадры", default=False)
    created_at = models.DateTimeField("Начата", auto_now_add=True)
    expires_at = models.DateTimeField("Действует до")
    completed_at = models.DateTimeField("Завершена", null=True, blank=True)

    class Meta:
        verbose_name = "Проверка «живости»"
        verbose_name_plural = "Проверки «живости»"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_purpose_display()} #{self.pk} — {self.user} — {self.get_status_display()}"


class LivenessFrame(models.Model):
    check_run = models.ForeignKey(
        LivenessCheck, verbose_name="Проверка", on_delete=models.CASCADE, related_name="frames"
    )
    step = models.CharField("Движение", max_length=20)
    file = models.ImageField("Кадр", storage=private_document_storage, upload_to=document_upload_path)
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Кадр проверки"
        verbose_name_plural = "Кадры проверки"
        constraints = [
            models.UniqueConstraint(fields=["check_run", "step"], name="one_frame_per_step")
        ]

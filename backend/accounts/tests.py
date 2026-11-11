import os
import shutil
import tempfile
import warnings
from datetime import date, timedelta
from io import BytesIO, StringIO
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from cars.models import Car, Tariff

from . import verification as service
from .factories import image_file, make_driver, registry_for
from .kyc import make_personal_number
from .models import (
    ClassRequirement,
    DriverVerification,
    User,
    VerificationDocument,
    VerificationEvent,
    VerificationStatus,
)

TMP_PRIVATE = tempfile.mkdtemp(prefix="ruli-private-")


def years_ago(years, extra_days=0):
    today = timezone.localdate()
    return service.add_years(today, -years) - timedelta(days=extra_days)


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class VerificationFlowTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(
            username="newbie", email="newbie@example.com", password="StrongPass123",
            first_name="Иван", last_name="Новый",
            phone_number="+375291230000", phone_verified_at=timezone.now(),
        )
        self.client.force_authenticate(self.user)
        registry_for("5AB 654321", "Новый Иван Петрович", date(1995, 4, 1), date(2020, 5, 5),
                     date(2030, 5, 5), date(2015, 6, 1))

    def fill_draft(self, **overrides):
        self.client.post("/api/verification/")
        data = {
            "full_name_on_document": "Новый Иван Петрович",
            "date_of_birth": "1995-04-01",
            "license_number": "5AB 654321",
            "license_issued_on": "2020-05-05",
            "license_expires_on": "2030-05-05",
            "category_b_since": "2015-06-01",
            "personal_number": make_personal_number(date(1995, 4, 1)),
            "consent": True,
            "biometric_consent": True,
            **overrides,
        }
        return self.client.patch("/api/verification/", data, format="json")

    def pass_liveness(self):
        check = self.client.post("/api/verification/liveness/").data
        frames = {step["code"]: image_file(f"{step['code']}.jpg", kind="scene") for step in check["steps"]}
        response = self.client.post(f"/api/verification/liveness/{check['id']}/", frames, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def upload_all(self):
        for kind in VerificationDocument.Kind.values:
            response = self.client.put(
                f"/api/verification/documents/{kind}/", {"file": image_file()}, format="multipart"
            )
            self.assertEqual(response.status_code, 200, response.data)

    def test_full_flow_from_draft_to_approval(self):
        self.fill_draft()
        self.upload_all()
        self.pass_liveness()
        response = self.client.post("/api/verification/submit/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["verification"]["status"], "pending")
        self.assertEqual(response.data["access"]["level"], 1)

        again = self.client.post("/api/verification/submit/")
        self.assertEqual(again.status_code, 400)

        verification = self.user.verifications.get()
        service.approve(verification, reviewer=None)
        me = self.client.get("/api/auth/me/").data
        self.assertTrue(me["is_verified"])
        self.assertEqual(me["access"]["level"], 2)
        self.assertEqual(me["driving_since"], "2015-06-01")

    def test_submit_without_documents_lists_failed_checks(self):
        self.fill_draft()
        response = self.client.post("/api/verification/submit/")
        self.assertEqual(response.status_code, 400)
        codes = {check["code"] for check in response.data["checks"]}
        self.assertIn("files_complete", codes)

    def test_needs_fix_allows_reshooting_only_flagged_photo(self):
        self.fill_draft()
        self.upload_all()
        self.pass_liveness()
        self.client.post("/api/verification/submit/")
        verification = self.user.verifications.get()
        service.request_fix(verification, None, "blurry_photo", kinds=["selfie_with_license"])

        accepted = self.client.put(
            "/api/verification/documents/license_front/", {"file": image_file()}, format="multipart"
        )
        self.assertEqual(accepted.status_code, 400)
        reshoot = self.client.put(
            "/api/verification/documents/selfie_with_license/", {"file": image_file()}, format="multipart"
        )
        self.assertEqual(reshoot.status_code, 200)
        self.assertEqual(self.client.post("/api/verification/submit/").status_code, 200)
        self.assertEqual(verification.documents.count(), 4)

    def test_documents_are_private_and_stripped_of_exif(self):
        self.fill_draft()
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # Make
        self.client.put(
            "/api/verification/documents/license_front/",
            {"file": image_file(exif=exif)},
            format="multipart",
        )
        document = VerificationDocument.objects.get()
        self.assertTrue(document.file.path.startswith(TMP_PRIVATE))
        self.assertFalse(document.file.path.startswith(str(settings.MEDIA_ROOT)))
        with Image.open(document.file.path) as stored:
            self.assertEqual(len(stored.getexif()), 0)

        other = User.objects.create_user(username="spy", email="spy@example.com", password="StrongPass123")
        self.client.force_authenticate(other)
        response = self.client.get("/api/verification/documents/license_front/")
        self.assertEqual(response.status_code, 404)

        self.client.force_authenticate(None)
        admin_url = f"/admin/accounts/driververification/{document.verification_id}/document/license_front/"
        self.assertNotEqual(self.client.get(admin_url).status_code, 200)

    def test_not_an_image_is_rejected(self):
        self.fill_draft()
        fake = SimpleUploadedFile("passport.jpg", b"not really a jpeg", content_type="image/jpeg")
        response = self.client.put(
            "/api/verification/documents/passport_main/", {"file": fake}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)

    def test_withdraw_consent_deletes_files(self):
        self.fill_draft()
        self.upload_all()
        path = VerificationDocument.objects.first().file.path
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/api/verification/consent/withdraw/")
        self.assertEqual(VerificationDocument.objects.count(), 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_status, VerificationStatus.NONE)
        self.assertFalse(os.path.exists(path))

    def test_failed_withdrawal_keeps_documents_and_files(self):
        self.fill_draft()
        self.upload_all()
        document = VerificationDocument.objects.first()
        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch.object(self.user, "save", side_effect=RuntimeError):
                with self.assertRaises(RuntimeError):
                    service.withdraw_consent(self.user)
        # Транзакция откатилась: строка вернулась — и файл на диске тоже на месте.
        self.assertTrue(VerificationDocument.objects.filter(pk=document.pk).exists())
        self.assertTrue(os.path.exists(document.file.path))

    def test_oversized_image_is_rejected_before_decoding(self):
        self.fill_draft()
        # 30 Мп отсекает своя проверка, 60 Мп — сам Pillow (больше 2 × MAX_IMAGE_PIXELS).
        for size in ((6000, 5000), (10000, 6000)):
            with self.subTest(size=size):
                buffer = BytesIO()
                Image.new("1", size).save(buffer, "PNG")  # файл — несколько килобайт
                bomb = SimpleUploadedFile("bomb.png", buffer.getvalue(), content_type="image/png")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                    response = self.client.put(
                        "/api/verification/documents/license_front/", {"file": bomb}, format="multipart"
                    )
                self.assertEqual(response.status_code, 400)
                self.assertIn("25 мегапикселей", str(response.data))
                self.assertFalse(VerificationDocument.objects.exists())

    # --- согласия ---

    def test_documents_require_consent_first(self):
        self.fill_draft(consent=False, biometric_consent=False)
        url = "/api/verification/documents/{}/"
        response = self.client.put(url.format("license_front"), {"file": image_file()}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "consent_required")

        self.client.patch("/api/verification/", {"consent": True}, format="json")
        response = self.client.put(url.format("license_front"), {"file": image_file()}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        # Селфи — биометрия: нужно отдельное согласие.
        selfie = self.client.put(url.format("selfie_with_license"), {"file": image_file()}, format="multipart")
        self.assertEqual(selfie.status_code, 400)
        self.assertEqual(selfie.data["code"], "consent_required")

        self.client.patch("/api/verification/", {"biometric_consent": True}, format="json")
        selfie = self.client.put(url.format("selfie_with_license"), {"file": image_file()}, format="multipart")
        self.assertEqual(selfie.status_code, 200, selfie.data)

    def test_withdrawing_consent_in_draft_deletes_documents(self):
        self.fill_draft()
        self.upload_all()
        selfie_path = VerificationDocument.objects.get(kind=VerificationDocument.Kind.SELFIE).file.path

        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch("/api/verification/", {"biometric_consent": False}, format="json")
        kinds = set(VerificationDocument.objects.values_list("kind", flat=True))
        self.assertEqual(len(kinds), 3)
        self.assertNotIn(VerificationDocument.Kind.SELFIE, kinds)
        self.assertFalse(os.path.exists(selfie_path))

        paths = [document.file.path for document in VerificationDocument.objects.all()]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch("/api/verification/", {"consent": False}, format="json")
        self.assertEqual(response.data["verification"]["documents"], [])
        self.assertFalse(VerificationDocument.objects.exists())
        self.assertFalse(any(os.path.exists(path) for path in paths))

    # --- блокировка ---

    def test_blocked_user_cannot_reapply_and_stays_blocked(self):
        self.fill_draft()
        self.upload_all()
        path = VerificationDocument.objects.first().file.path
        User.objects.filter(pk=self.user.pk).update(
            verification_status=VerificationStatus.BLOCKED, license_key="5AB654321"
        )
        self.user.refresh_from_db()

        responses = [
            self.client.post("/api/verification/"),
            self.client.put(
                "/api/verification/documents/license_front/", {"file": image_file()}, format="multipart"
            ),
            self.client.post("/api/verification/submit/"),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data["code"], "blocked")

        # Отзыв согласия удаляет файлы, но блокировку не снимает.
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/api/verification/consent/withdraw/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.verification_status, VerificationStatus.BLOCKED)
        self.assertIsNone(self.user.license_key)
        self.assertFalse(os.path.exists(path))

    # --- лимит загрузок ---

    def test_only_uploads_count_against_upload_limit(self):
        self.fill_draft()
        url = "/api/verification/documents/{}/"
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"verification_upload": "1/hour"}):
            first = self.client.put(url.format("license_front"), {"file": image_file()}, format="multipart")
            self.assertEqual(first.status_code, 200, first.data)
            for _ in range(3):
                preview = self.client.get(url.format("license_front"))
                # Дочитываем поток: тестовый клиент сам закроет файл (на Windows иначе не удалить).
                # Прямой preview.close() шлёт request_finished и рвёт соединение с MySQL посреди теста.
                b"".join(preview.streaming_content)
                self.assertEqual(preview.status_code, 200)
            self.assertEqual(self.client.delete(url.format("license_front")).status_code, 200)
            second = self.client.put(url.format("license_back"), {"file": image_file()}, format="multipart")
            self.assertEqual(second.status_code, 429)

    def test_driver_data_is_read_only_through_profile(self):
        response = self.client.patch("/api/auth/me/", {"date_of_birth": "2010-01-01"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.date_of_birth)


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class RetentionTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def verification(self, status, **fields):
        number = DriverVerification.objects.count()
        user = User.objects.create(username=f"keep{number}", email=f"keep{number}@example.com")
        return DriverVerification.objects.create(user=user, status=status, **fields)

    def add_document(self, verification, kind=VerificationDocument.Kind.LICENSE_FRONT):
        document = VerificationDocument(verification=verification, kind=kind, sha256="0" * 64)
        document.file.save("scan.jpg", ContentFile(b"scan"), save=True)
        return document.file.path

    def purge(self):
        # Файлы удаляются после коммита — в TestCase колбэки нужно выполнить вручную.
        with self.captureOnCommitCallbacks(execute=True):
            call_command("purge_verification_files", stdout=StringIO())

    def test_purges_documents_after_retention_period(self):
        S = DriverVerification.Status
        now = timezone.now()
        old = now - timedelta(days=settings.VERIFICATION_RETENTION_DAYS + 1)
        approved = self.verification(S.APPROVED, reviewed_at=old)
        superseded = self.verification(S.SUPERSEDED, reviewed_at=old)
        abandoned = self.verification(S.DRAFT)
        abandoned_fix = self.verification(S.NEEDS_FIX, reviewed_at=old)
        fresh = self.verification(S.REJECTED, reviewed_at=now - timedelta(days=1))
        pending = self.verification(S.PENDING, submitted_at=old)
        active_draft = self.verification(S.DRAFT)
        # Модератор вернул давно, но водитель недавно переснял фото — заявка жива.
        active_fix = self.verification(S.NEEDS_FIX, reviewed_at=old)
        everything = (approved, superseded, abandoned, abandoned_fix, fresh, pending, active_draft, active_fix)
        paths = {verification.pk: self.add_document(verification) for verification in everything}
        DriverVerification.objects.filter(pk__in=(abandoned.pk, abandoned_fix.pk)).update(updated_at=old)

        self.purge()
        for verification in (approved, superseded, abandoned, abandoned_fix):
            verification.refresh_from_db()
            self.assertIsNotNone(verification.files_purged_at)
            self.assertFalse(verification.documents.exists())
            self.assertFalse(os.path.exists(paths[verification.pk]))
            self.assertTrue(verification.events.filter(action=VerificationEvent.Action.FILES_PURGED).exists())
        for verification in (fresh, pending, active_draft, active_fix):
            verification.refresh_from_db()
            self.assertIsNone(verification.files_purged_at)
            self.assertTrue(verification.documents.exists())
            self.assertTrue(os.path.exists(paths[verification.pk]))

        # Повторный запуск уже очищенные заявки не трогает.
        self.purge()
        purged = VerificationEvent.objects.filter(action=VerificationEvent.Action.FILES_PURGED)
        self.assertEqual(purged.count(), 4)

    def test_failed_purge_keeps_documents_and_files(self):
        old = timezone.now() - timedelta(days=settings.VERIFICATION_RETENTION_DAYS + 1)
        verification = self.verification(DriverVerification.Status.APPROVED, reviewed_at=old)
        path = self.add_document(verification)
        command_log = "accounts.management.commands.purge_verification_files.log"
        with mock.patch(command_log, side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.purge()
        # Откат транзакции вернул строку — файл, на который она ссылается, тоже цел.
        verification.refresh_from_db()
        self.assertIsNone(verification.files_purged_at)
        self.assertTrue(verification.documents.exists())
        self.assertTrue(os.path.exists(path))

    def test_deleting_request_removes_files_after_commit(self):
        verification = self.verification(DriverVerification.Status.REJECTED)
        path = self.add_document(verification)
        with self.captureOnCommitCallbacks(execute=True):
            verification.delete()
        self.assertFalse(os.path.exists(path))

    def test_admin_keeps_audit_log_but_can_delete_request(self):
        boss = User.objects.create_superuser("boss", "boss@example.com", "StrongPass123")
        self.client.force_login(boss)
        verification = self.verification(DriverVerification.Status.REJECTED)
        path = self.add_document(verification)
        service.log(verification, VerificationEvent.Action.DOCUMENT_VIEWED, boss, kind="license_front")
        event = VerificationEvent.objects.get()

        response = self.client.get(f"/admin/accounts/verificationevent/{event.pk}/delete/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/admin/accounts/verificationevent/").status_code, 200)
        change_url = f"/admin/accounts/driververification/{verification.pk}/change/"
        self.assertEqual(self.client.get(change_url).status_code, 200)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/admin/accounts/driververification/{verification.pk}/delete/", {"post": "yes"}
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DriverVerification.objects.filter(pk=verification.pk).exists())
        self.assertFalse(os.path.exists(path))


class AuthThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    def login(self, forwarded_for):
        return self.client.post(
            "/api/auth/token/",
            {"username": "ghost", "password": "wrong"},
            format="json",
            HTTP_X_FORWARDED_FOR=forwarded_for,
        )

    def test_login_attempts_are_limited_per_client_address(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"login": "1/min"}):
            self.assertEqual(self.login("198.51.100.7").status_code, 401)
            self.assertEqual(self.login("198.51.100.7").status_code, 429)
            # Подставленный клиентом адрес в начале заголовка не помогает: nginx дописывает настоящий.
            self.assertEqual(self.login("203.0.113.1, 198.51.100.7").status_code, 429)
            self.assertEqual(self.login("198.51.100.8").status_code, 401)

    def test_registration_is_limited(self):
        def register(name, phone):
            return self.client.post(
                "/api/auth/register/",
                {
                    "username": name,
                    "email": f"{name}@example.com",
                    "password": "StrongPass123",
                    "password_confirm": "StrongPass123",
                    "first_name": "Иван",
                    "last_name": "Иванов",
                    "phone_number": phone,
                },
                format="json",
            )

        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"register": "1/hour"}):
            self.assertEqual(register("first", "+375291110001").status_code, 201)
            self.assertEqual(register("second", "+375291110002").status_code, 429)


class AutoCheckTests(APITestCase):
    def check_codes(self, **fields):
        user = User.objects.create_user(username=f"u{User.objects.count()}", email=f"u{User.objects.count()}@e.com", password="x")
        base = dict(
            full_name_on_document="Иванов Иван",
            date_of_birth=date(1995, 1, 1),
            license_number="5AB 123456",
            license_issued_on=date(2020, 1, 1),
            license_expires_on=date(2030, 1, 1),
            category_b_since=date(2015, 1, 1),
        )
        base.update(fields)
        verification = DriverVerification.objects.create(user=user, **base)
        return {check["code"]: check["level"] for check in service.run_auto_checks(verification)}

    def test_underage(self):
        codes = self.check_codes(date_of_birth=years_ago(17), category_b_since=years_ago(1))
        self.assertEqual(codes["age_min"], "fail")

    def test_license_issued_in_future(self):
        future = timezone.localdate() + timedelta(days=10)
        codes = self.check_codes(license_issued_on=future, license_expires_on=future + timedelta(days=3650))
        self.assertEqual(codes["license_dates"], "fail")

    def test_category_b_before_sixteen(self):
        codes = self.check_codes(date_of_birth=date(2000, 1, 1), category_b_since=date(2015, 6, 1))
        self.assertEqual(codes["license_dates"], "fail")

    def test_expired_license(self):
        codes = self.check_codes(license_issued_on=date(2010, 1, 1), license_expires_on=date(2020, 1, 1))
        self.assertEqual(codes["license_not_expired"], "fail")

    def test_unusual_number_format_is_only_a_warning(self):
        codes = self.check_codes(license_number="12345")
        self.assertEqual(codes["license_number_format"], "warn")

    def test_duplicate_license_fails(self):
        make_driver("owner", license_number="5AB 777777")
        codes = self.check_codes(license_number="5АВ 777777")  # кириллические «А» и «В»
        self.assertEqual(codes["duplicate_license"], "fail")


class AccessPolicyTests(APITestCase):
    def setUp(self):
        tariff = Tariff.objects.create(name="Комфорт", price_per_minute="0.37")
        self.cars = {
            car_class: Car.objects.create(
                brand="Geely", model=car_class, year=2023, license_plate=f"{i}000 AA-7",
                car_class=car_class, tariff=tariff, latitude=53.9, longitude=27.56,
            )
            for i, car_class in enumerate(["economy", "comfort", "business", "premium"], start=1)
        }

    def test_young_driver_sees_unlock_dates(self):
        novice = make_driver("novice", dob=years_ago(20, 30), driving_since=years_ago(1, 180))
        ClassRequirement.objects.filter(car_class="business").update(min_completed_rentals=0)
        policy = service.access_policy(novice)
        classes = policy["classes"]
        self.assertTrue(classes["economy"]["allowed"])
        self.assertTrue(classes["comfort"]["allowed"])
        self.assertFalse(classes["business"]["allowed"])
        self.assertEqual(set(classes["business"]["reasons"]), {"age", "experience"})
        expected = max(
            service.add_years(novice.date_of_birth, 21), service.add_years(novice.driving_since, 2)
        )
        self.assertEqual(classes["business"]["unlock_on"], expected)
        self.assertIn("trips", classes["premium"]["reasons"])
        self.assertEqual(policy["level"], 2)

    def test_reserve_respects_access(self):
        newbie = User.objects.create_user(username="nobody", email="n@e.com", password="StrongPass123")
        self.client.force_authenticate(newbie)
        response = self.client.post("/api/rentals/", {"car": self.cars["economy"].id}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "verification_required")

        novice = make_driver("novice", dob=years_ago(20, 30), driving_since=years_ago(1, 180))
        self.client.force_authenticate(novice)
        locked = self.client.post("/api/rentals/", {"car": self.cars["premium"].id}, format="json")
        self.assertEqual(locked.status_code, 403)
        self.assertEqual(locked.data["code"], "class_locked")
        ok = self.client.post("/api/rentals/", {"car": self.cars["economy"].id}, format="json")
        self.assertEqual(ok.status_code, 201)

    def test_expired_license_blocks_booking(self):
        driver = make_driver("old", expires=timezone.localdate() - timedelta(days=1))
        self.assertEqual(service.access_policy(driver)["status"], VerificationStatus.EXPIRED)
        self.client.force_authenticate(driver)
        response = self.client.post("/api/rentals/", {"car": self.cars["economy"].id}, format="json")
        self.assertEqual(response.data["code"], "license_expired")

    def test_catalog_shows_eligibility(self):
        novice = make_driver("novice", dob=years_ago(20, 30), driving_since=years_ago(1, 180))
        self.client.force_authenticate(novice)
        cars = {car["car_class"]: car for car in self.client.get("/api/cars/").data["results"]}
        self.assertTrue(cars["economy"]["eligibility"]["allowed"])
        self.assertFalse(cars["premium"]["eligibility"]["allowed"])

        self.client.force_authenticate(None)
        anon = self.client.get("/api/cars/").data["results"][0]
        self.assertEqual(anon["eligibility"]["code"], "login_required")

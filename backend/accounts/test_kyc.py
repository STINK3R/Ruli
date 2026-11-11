"""Строгий KYC: SMS-код, личный номер, реестр ГАИ, «живость», проверка лица перед поездкой."""

import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageEnhance
from rest_framework.test import APITestCase

from cars.models import Car, Tariff

from . import kyc
from . import verification as service
from .factories import image_file, make_driver, registry_for
from .models import DriverVerification, LicenseRegistryRecord, LivenessCheck, User, VerificationStatus

TMP_PRIVATE = tempfile.mkdtemp(prefix="ruli-kyc-")


def jpeg(image, name="frame.jpg"):
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class PersonalNumberTests(APITestCase):
    def test_generated_number_round_trips(self):
        number = kyc.make_personal_number(date(1989, 5, 15), "m", region="A", serial=1)
        self.assertEqual(number[:8], "3150589A")
        birth, sex, citizenship = kyc.parse_personal_number(number)
        self.assertEqual((birth, sex, citizenship), (date(1989, 5, 15), "m", "PB"))

    def test_century_and_sex_are_encoded(self):
        self.assertTrue(kyc.make_personal_number(date(2003, 1, 2), "f").startswith("6020103"))

    def test_typo_breaks_check_digit(self):
        number = kyc.make_personal_number(date(1990, 7, 1))
        broken = number[:9] + ("2" if number[9] != "2" else "3") + number[10:]
        with self.assertRaisesMessage(ValueError, "ошибка"):
            kyc.parse_personal_number(broken)

    def test_impossible_date_is_rejected(self):
        body = "3320190H001PB"  # 32 января
        with self.assertRaises(ValueError):
            kyc.parse_personal_number(body + str(kyc.check_digit(body)))

    def test_cyrillic_letters_are_normalized(self):
        number = kyc.make_personal_number(date(1990, 7, 1), region="H")
        cyrillic = number.replace("H", "Н").replace("PB", "РВ")
        self.assertEqual(kyc.normalize_personal_number(cyrillic), number)


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class StrictSubmitTests(APITestCase):
    """Заявку с выдуманными данными автопроверки не пропускают до модератора."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="kyc", email="kyc@example.com", password="StrongPass123",
            first_name="Анна", last_name="Петрова", phone_number="+375297776655",
            phone_verified_at=timezone.now(),
        )
        self.client.force_authenticate(self.user)
        self.dob = date(1996, 2, 29)
        self.record = registry_for("4KM 202020", "Петрова Анна Сергеевна", self.dob, date(2019, 3, 1),
                                   date(2029, 3, 1), date(2015, 4, 1))
        self.client.post("/api/verification/")

    def fill(self, **overrides):
        data = {
            "full_name_on_document": "Петрова Анна Сергеевна",
            "date_of_birth": self.dob.isoformat(),
            "personal_number": kyc.make_personal_number(self.dob, "f"),
            "license_number": "4KM 202020",
            "license_issued_on": "2019-03-01",
            "license_expires_on": "2029-03-01",
            "category_b_since": "2015-04-01",
            "consent": True,
            "biometric_consent": True,
            **overrides,
        }
        response = self.client.patch("/api/verification/", data, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        for kind in ("license_front", "license_back", "passport_main", "selfie_with_license"):
            self.client.put(f"/api/verification/documents/{kind}/", {"file": image_file()}, format="multipart")

    def liveness(self, frames=None):
        check = self.client.post("/api/verification/liveness/").data
        files = frames or {step["code"]: image_file(f"{step['code']}.jpg", kind="scene") for step in check["steps"]}
        return check, self.client.post(f"/api/verification/liveness/{check['id']}/", files, format="multipart")

    def failed_codes(self):
        response = self.client.post("/api/verification/submit/")
        self.assertEqual(response.status_code, 400, response.data)
        return {check["code"] for check in response.data["checks"]}

    def test_honest_application_reaches_moderator(self):
        self.fill()
        self.assertEqual(self.liveness()[1].status_code, 200)
        response = self.client.post("/api/verification/submit/")
        self.assertEqual(response.status_code, 200, response.data)
        verification = self.user.verifications.get()
        self.assertEqual(verification.status, DriverVerification.Status.PENDING)
        self.assertLess(verification.risk_score, 50)

    def test_without_liveness_submit_fails(self):
        self.fill()
        self.assertIn("liveness", self.failed_codes())

    def test_unknown_license_number_fails(self):
        self.fill(license_number="4KM 999999")
        self.liveness()
        self.assertIn("registry_not_found", self.failed_codes())

    def test_someone_elses_license_fails(self):
        registry_for("2AB 111111", "Сидоров Олег", date(1980, 1, 1), date(2019, 3, 1), date(2029, 3, 1))
        self.fill(license_number="2AB 111111")
        self.liveness()
        codes = self.failed_codes()
        self.assertIn("registry_name", codes)
        self.assertIn("registry_birth", codes)

    def test_suspended_license_fails(self):
        self.record.status = LicenseRegistryRecord.Status.SUSPENDED
        self.record.save()
        self.fill()
        self.liveness()
        self.assertIn("registry_suspended", self.failed_codes())

    def test_personal_number_must_match_birth_date(self):
        self.fill(personal_number=kyc.make_personal_number(date(1990, 1, 1), "f"))
        self.liveness()
        self.assertIn("personal_number_birth", self.failed_codes())

    def test_unverified_phone_fails(self):
        User.objects.filter(pk=self.user.pk).update(phone_verified_at=None)
        self.fill()
        self.liveness()
        self.assertIn("phone", self.failed_codes())

    def test_same_photo_shown_to_camera_fails_liveness(self):
        """Фото, поднесённое к камере: кадры почти одинаковые — движения нет."""
        self.fill()
        base = Image.effect_noise((640, 480), 40).convert("RGB")
        check = self.client.post("/api/verification/liveness/").data
        frames = {
            step["code"]: jpeg(ImageEnhance.Brightness(base).enhance(1 + index * 0.005), f"{index}.jpg")
            for index, step in enumerate(check["steps"])
        }
        response = self.client.post(f"/api/verification/liveness/{check['id']}/", frames, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "liveness_failed")
        self.assertEqual(LivenessCheck.objects.get(pk=check["id"]).status, LivenessCheck.Status.FAILED)

    def test_expired_liveness_is_rejected(self):
        self.fill()
        check = self.client.post("/api/verification/liveness/").data
        LivenessCheck.objects.filter(pk=check["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        frames = {step["code"]: image_file() for step in check["steps"]}
        response = self.client.post(f"/api/verification/liveness/{check['id']}/", frames, format="multipart")
        self.assertEqual(response.data["code"], "liveness_expired")

    def test_steps_are_random_and_start_with_center(self):
        self.fill()
        sequences = {tuple(s["code"] for s in self.client.post("/api/verification/liveness/").data["steps"])
                     for _ in range(6)}
        self.assertTrue(all(seq[0] == "center" and len(seq) == 4 for seq in sequences))
        self.assertGreater(len(sequences), 1)

    @override_settings(KYC_DEMO_MODE=False)
    def test_demo_images_are_refused_in_production_mode(self):
        self.fill()
        response = self.client.put(
            "/api/verification/documents/license_front/", {"file": image_file(), "demo": "1"}, format="multipart"
        )
        self.assertEqual(response.data["code"], "demo_disabled")
        self.assertEqual(self.client.get("/api/verification/demo-profile/").status_code, 404)

    def test_demo_persona_passes_registry_and_is_flagged(self):
        persona = self.client.get("/api/verification/demo-profile/").data
        self.assertEqual(self.client.get("/api/verification/demo-profile/").data, persona)  # одна запись на аккаунт
        response = self.client.patch("/api/verification/", {**persona, "consent": True, "biometric_consent": True},
                                     format="json")
        self.assertEqual(response.status_code, 200, response.data)
        for kind in ("license_front", "license_back", "passport_main", "selfie_with_license"):
            self.client.put(f"/api/verification/documents/{kind}/", {"file": image_file(), "demo": "1"},
                            format="multipart")
        self.liveness()
        self.assertEqual(self.client.post("/api/verification/submit/").status_code, 200)
        verification = self.user.verifications.get()
        self.assertIn("demo_documents", {c["code"] for c in verification.auto_checks})
        self.assertGreaterEqual(verification.risk_score, 30)


class PhoneCodeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="phone", email="phone@example.com", password="StrongPass123", phone_number="+375295550011"
        )
        self.client.force_authenticate(self.user)

    def test_code_confirms_phone(self):
        sent = self.client.post("/api/auth/phone/send/").data
        self.assertEqual(len(sent["demo_code"]), 6)
        wrong = "000000" if sent["demo_code"] != "000000" else "111111"
        bad = self.client.post("/api/auth/phone/confirm/", {"code": wrong}, format="json")
        self.assertEqual(bad.data["code"], "code_wrong")
        ok = self.client.post("/api/auth/phone/confirm/", {"code": sent["demo_code"]}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertTrue(ok.data["phone_verified"])

    def test_resend_has_cooldown(self):
        self.client.post("/api/auth/phone/send/")
        again = self.client.post("/api/auth/phone/send/")
        self.assertEqual(again.data["code"], "cooldown")

    def test_attempts_are_limited(self):
        sent = self.client.post("/api/auth/phone/send/").data
        wrong = "000000" if sent["demo_code"] != "000000" else "111111"
        for _ in range(5):
            self.client.post("/api/auth/phone/confirm/", {"code": wrong}, format="json")
        locked = self.client.post("/api/auth/phone/confirm/", {"code": sent["demo_code"]}, format="json")
        self.assertEqual(locked.data["code"], "code_locked")

    @override_settings(SMS_DEMO_MODE=False)
    def test_code_is_not_returned_in_production_mode(self):
        self.assertNotIn("demo_code", self.client.post("/api/auth/phone/send/").data)

    def test_code_is_stored_only_as_hash(self):
        code = self.client.post("/api/auth/phone/send/").data["demo_code"]
        self.assertNotIn(code, self.user.phone_codes.get().code_hash)

    def test_registration_requires_belarusian_mobile(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "fake", "email": "fake@example.com", "password": "StrongPass123",
                "password_confirm": "StrongPass123", "first_name": "А", "last_name": "Б",
                "phone_number": "+79990000000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)


class AfterApprovalTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.tariff = Tariff.objects.create(name="Эконом", price_per_minute=Decimal("0.29"))
        self.car = Car.objects.create(
            brand="Kia", model="Rio", year=2023, license_plate="1234 AB-7", car_class="economy",
            tariff=self.tariff, latitude=53.9, longitude=27.56,
        )
        self.driver = make_driver("approved", license_number="5AB 300300")
        self.client.force_authenticate(self.driver)

    def test_name_is_locked_after_approval(self):
        response = self.client.patch("/api/auth/me/", {"last_name": "Другой"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("last_name", response.data)

    def test_changed_phone_blocks_booking_until_confirmed(self):
        self.client.patch("/api/auth/me/", {"phone_number": "+375447001122"}, format="json")
        response = self.client.post("/api/rentals/", {"car": self.car.id}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "phone_required")
        self.assertNotIn("unlock_on", response.data)

    def test_suspension_in_registry_closes_trips(self):
        registry_for("5AB 300300", "Иванов Иван", date(1990, 1, 1), date(2010, 1, 1), date(2035, 1, 1),
                     status=LicenseRegistryRecord.Status.SUSPENDED)
        self.assertEqual(service.access_policy(self.driver)["status"], VerificationStatus.LICENSE_INVALID)
        response = self.client.post("/api/rentals/", {"car": self.car.id}, format="json")
        self.assertEqual(response.data["code"], "license_invalid")


@override_settings(PRIVATE_MEDIA_ROOT=TMP_PRIVATE, INSPECTIONS_REQUIRED=False, TRIP_FACE_CHECK_REQUIRED=True)
class TripFaceCheckTests(APITestCase):
    def setUp(self):
        cache.clear()
        tariff = Tariff.objects.create(name="Эконом", price_per_minute=Decimal("0.29"))
        self.car = Car.objects.create(
            brand="Kia", model="Rio", year=2023, license_plate="4321 AB-7", car_class="economy",
            tariff=tariff, latitude=53.9, longitude=27.56,
        )
        self.driver = make_driver("trip")
        self.client.force_authenticate(self.driver)
        self.rental = self.client.post("/api/rentals/", {"car": self.car.id}, format="json").data

    def test_trip_starts_only_after_face_check(self):
        url = f"/api/rentals/{self.rental['id']}/"
        blocked = self.client.post(url + "start/")
        self.assertEqual(blocked.data["code"], "face_check_required")

        check = self.client.post(url + "face-check/start/").data
        self.assertEqual(len(check["steps"]), 2)
        frames = {step["code"]: image_file(kind="scene") for step in check["steps"]}
        passed = self.client.post(url + "face-check/", {"check": check["id"], **frames}, format="multipart")
        self.assertEqual(passed.status_code, 200, passed.data)
        self.assertTrue(passed.data["face_check"]["passed"])
        self.assertEqual(self.client.post(url + "start/").status_code, 200)

    def test_someone_elses_check_cannot_be_used(self):
        other = make_driver("other")
        self.client.force_authenticate(other)
        foreign = kyc.start_liveness(other, LivenessCheck.Purpose.TRIP)
        self.client.force_authenticate(self.driver)
        response = self.client.post(
            f"/api/rentals/{self.rental['id']}/face-check/",
            {"check": foreign.id, "center": image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

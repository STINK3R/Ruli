import shutil
import tempfile
import warnings
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from accounts.factories import image_file, make_driver
from cars.models import Car, Tariff
from rentals.models import Rental

from .chain import verify_chain
from .models import Damage, Inspection, InspectionPhoto
from .services import open_claim

TMP_MEDIA = tempfile.mkdtemp(prefix="ruli-media-")
ANGLES = ("front", "rear", "left", "right")


def photos(**overrides):
    files = {angle: image_file(f"{angle}.jpg") for angle in ANGLES}
    files.update(overrides)
    return files


@override_settings(MEDIA_ROOT=TMP_MEDIA, INSPECTIONS_REQUIRED=True, TRIP_FACE_CHECK_REQUIRED=False)
class InspectionTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.tariff = Tariff.objects.create(name="Комфорт", price_per_minute=Decimal("0.37"))
        self.car = Car.objects.create(
            brand="Geely", model="Emgrand", year=2023, license_plate="8743 AB-7", tariff=self.tariff,
            car_class=Car.CarClass.COMFORT, latitude=53.9213, longitude=27.5817,
            livery=Car.Livery.IVORY,
        )
        self.user = make_driver("client")
        self.client.force_authenticate(self.user)

    def book(self):
        response = self.client.post("/api/rentals/", {"car": self.car.id}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def inspect(self, rental_id, kind="start", files=None, **data):
        payload = {"kind": kind, **(files if files is not None else photos()), **data}
        return self.client.post(f"/api/rentals/{rental_id}/inspections/", payload, format="multipart")

    def drive(self, minutes=10):
        """Полный цикл с осмотрами; возвращает аренду, сдвинутую в прошлое на minutes."""
        rental_id = self.book()
        self.assertEqual(self.inspect(rental_id).status_code, 201)
        self.client.post(f"/api/rentals/{rental_id}/start/")
        self.assertEqual(self.inspect(rental_id, "finish").status_code, 201)
        self.client.post(f"/api/rentals/{rental_id}/finish/")
        return Rental.objects.get(pk=rental_id)

    # --- качество фото ---

    def test_dark_photo_is_rejected(self):
        rental_id = self.book()
        response = self.inspect(rental_id, files=photos(front=image_file(kind="dark")))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "too_dark")

    def test_flat_photo_is_rejected_as_blurry(self):
        rental_id = self.book()
        response = self.inspect(rental_id, files=photos(rear=image_file(kind="flat")))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "too_blurry")

    def test_all_four_angles_required(self):
        rental_id = self.book()
        files = photos()
        files.pop("left")
        response = self.inspect(rental_id, files=files)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["missing"], ["left"])

    def test_car_photos_from_the_site_pass_quality_check(self):
        from .quality import measure

        car_photo = Image.effect_noise((900, 500), 40).convert("RGB")
        brightness, sharpness = measure(car_photo)
        self.assertGreater(brightness, 40)
        self.assertGreater(sharpness, 6)

    def test_oversized_photo_is_rejected_before_decoding(self):
        rental_id = self.book()
        # 30 Мп отсекает своя проверка, 60 Мп — сам Pillow (больше 2 × MAX_IMAGE_PIXELS).
        for size in ((6000, 5000), (10000, 6000)):
            with self.subTest(size=size):
                buffer = BytesIO()
                Image.new("1", size).save(buffer, "PNG")  # файл — несколько килобайт
                bomb = SimpleUploadedFile("front.png", buffer.getvalue(), content_type="image/png")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                    response = self.inspect(rental_id, files=photos(front=bomb))
                self.assertEqual(response.status_code, 400)
                self.assertIn("25 мегапикселей", str(response.data["front"]))
                self.assertFalse(Inspection.objects.exists())

    def test_invalid_coordinates_are_not_stored(self):
        rental_id = self.book()
        self.assertEqual(self.inspect(rental_id, lat="95", lng="27.58").status_code, 201)
        start = Inspection.objects.get(kind="start")
        self.assertEqual((start.latitude, start.longitude), (None, None))

        self.client.post(f"/api/rentals/{rental_id}/start/")
        self.assertEqual(self.inspect(rental_id, "finish", lat="nan", lng="inf").status_code, 201)
        finish = Inspection.objects.get(kind="finish")
        self.assertEqual((finish.latitude, finish.longitude), (None, None))

        self.client.post(f"/api/rentals/{rental_id}/finish/")
        second = self.book()
        self.assertEqual(self.inspect(second, lat="53.9213", lng="27.5817").status_code, 201)
        stored = Inspection.objects.get(rental_id=second)
        self.assertEqual((stored.latitude, stored.longitude), (53.9213, 27.5817))

    # --- правила старта ---

    def test_start_requires_inspection_then_passes(self):
        rental_id = self.book()
        self.assertEqual(self.client.post(f"/api/rentals/{rental_id}/start/").data["code"], "inspection_required")
        self.assertEqual(self.inspect(rental_id).status_code, 201)
        self.assertEqual(self.client.post(f"/api/rentals/{rental_id}/start/").status_code, 200)
        finish = self.client.post(f"/api/rentals/{rental_id}/finish/")
        self.assertEqual(finish.data["code"], "inspection_required")

    def test_same_inspection_cannot_be_sealed_twice(self):
        rental_id = self.book()
        self.inspect(rental_id)
        self.assertEqual(self.inspect(rental_id).status_code, 400)

    # --- цепочка хэшей ---

    def test_chain_links_and_detects_tampering(self):
        self.drive()
        first, second = Inspection.objects.order_by("created_at", "id")
        self.assertEqual(second.prev_hash, first.seal_hash)
        self.assertTrue(verify_chain(self.car)["ok"])

        Inspection.objects.filter(pk=first.pk).update(latitude=55.75)
        result = verify_chain(self.car)
        self.assertFalse(result["ok"])
        self.assertEqual(result["broken_at"], first.pk)
        self.assertEqual(result["reason"], "record_modified")

    def test_replaced_photo_is_detected(self):
        self.drive()
        photo = InspectionPhoto.objects.order_by("id").first()
        with open(photo.image.path, "wb") as stream:
            stream.write(b"tampered")
        self.assertEqual(verify_chain(self.car)["reason"], "photo_modified")

    def test_passport_is_public(self):
        self.drive()
        self.client.force_authenticate(None)
        passport = self.client.get(f"/api/cars/{self.car.id}/passport/").data
        self.assertEqual(passport["chain_length"], 2)
        self.assertTrue(passport["integrity"]["ok"])
        self.assertTrue(passport["is_signature"])

    def test_new_act_resets_cached_integrity(self):
        rental_id = self.book()
        self.inspect(rental_id)
        url = f"/api/cars/{self.car.id}/passport/"
        self.assertEqual(self.client.get(url).data["integrity"]["checked"], 1)

        self.client.post(f"/api/rentals/{rental_id}/start/")
        with self.captureOnCommitCallbacks(execute=True):
            self.inspect(rental_id, "finish")
        self.assertEqual(self.client.get(url).data["integrity"]["checked"], 2)

    # --- повреждения и претензии ---

    def test_new_damage_is_attributed_to_previous_trip(self):
        previous = self.drive()
        rental_id = self.book()
        marks = '[{"x": 0.30, "y": 0.20, "severity": "dent", "angle": "front"}]'
        response = self.inspect(rental_id, damages=marks)
        self.assertEqual(len(response.data["new_damages"]), 1)
        damage = Damage.objects.get()
        self.assertEqual(damage.responsible_rental_id, previous.pk)

        # Отметка рядом с уже известной — не новое повреждение.
        self.client.post(f"/api/rentals/{rental_id}/start/")
        self.inspect(rental_id, "finish")
        self.client.post(f"/api/rentals/{rental_id}/finish/")
        third = self.book()
        response = self.inspect(third, damages='[{"x": 0.32, "y": 0.21, "severity": "dent"}]')
        self.assertEqual(response.data["new_damages"], [])

    def test_known_damage_marked_again_at_finish_is_not_blamed_on_trip(self):
        rental_id = self.book()
        self.inspect(rental_id, damages='[{"x": 0.30, "y": 0.20, "severity": "dent"}]')
        self.client.post(f"/api/rentals/{rental_id}/start/")
        response = self.inspect(rental_id, "finish", damages='[{"x": 0.31, "y": 0.21, "severity": "dent"}]')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["new_damages"], [])
        self.assertEqual(Damage.objects.count(), 1)
        self.assertFalse(Damage.objects.filter(responsible_rental_id=rental_id).exists())

    def test_claim_window_is_24_hours(self):
        previous = self.drive()
        rental_id = self.book()
        self.inspect(rental_id, damages='[{"x": 0.5, "y": 0.5, "severity": "scratch"}]')
        damage = Damage.objects.get()

        self.assertEqual(open_claim(damage, now=previous.finished_at + timedelta(hours=23)).status, "confirmed")
        damage.status = Damage.Status.NEW
        damage.save()
        with self.assertRaises(ValidationError):
            open_claim(damage, now=previous.finished_at + timedelta(hours=25))

    def test_damage_seen_before_trip_is_auto_rejected(self):
        previous = self.drive()
        damage = Damage.objects.create(
            car=self.car, x=0.4, y=0.4, severity="scratch",
            first_seen=Inspection.objects.order_by("created_at").first(),
            responsible_rental=previous,
        )
        Inspection.objects.filter(pk=damage.first_seen_id).update(
            created_at=previous.started_at - timedelta(minutes=5)
        )
        damage.refresh_from_db()
        self.assertEqual(open_claim(damage).status, "disputed")

    def test_confirmed_damage_blocks_plus_level(self):
        from accounts.verification import access_policy

        for _ in range(5):
            self.drive()
        self.assertEqual(access_policy(self.user)["level"], 3)
        Damage.objects.create(
            car=self.car, x=0.1, y=0.1, severity="dent", status=Damage.Status.CONFIRMED,
            first_seen=Inspection.objects.first(), responsible_rental=Rental.objects.first(),
        )
        self.assertEqual(access_policy(self.user)["level"], 2)

    # --- гарантия Signature ---

    def test_signature_dirty_car_gives_free_minutes(self):
        rental_id = self.book()
        response = self.inspect(rental_id, files=photos(interior=image_file("in.jpg")), cleanliness="3")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["rental"]["compensation_minutes"], 15)
        self.car.refresh_from_db()
        self.assertTrue(self.car.needs_cleaning)

    def test_dirty_without_interior_photo_is_rejected(self):
        rental_id = self.book()
        response = self.inspect(rental_id, cleanliness="3")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["missing"], ["interior"])

    def test_plain_car_gets_no_compensation(self):
        self.car.livery = Car.Livery.NONE
        self.car.save()
        rental_id = self.book()
        response = self.inspect(rental_id, files=photos(interior=image_file("in.jpg")), cleanliness="3")
        self.assertEqual(response.data["rental"]["compensation_minutes"], 0)

    def test_compensation_once_a_week(self):
        first = self.book()
        self.inspect(first, files=photos(interior=image_file("in.jpg")), cleanliness="3")
        self.client.post(f"/api/rentals/{first}/cancel/")
        second = self.book()
        response = self.inspect(second, files=photos(interior=image_file("in.jpg")), cleanliness="3")
        self.assertEqual(response.data["rental"]["compensation_minutes"], 0)

    def test_rental_shows_signature_guarantee_availability(self):
        minutes = settings.SIGNATURE_COMPENSATION_MINUTES
        first = self.book()
        guarantee = self.client.get(f"/api/rentals/{first}/").data["signature_guarantee"]
        self.assertEqual(guarantee, {"available": True, "minutes": minutes})

        self.inspect(first, files=photos(interior=image_file("in.jpg")), cleanliness="3")
        self.client.post(f"/api/rentals/{first}/cancel/")
        second = self.book()
        guarantee = self.client.get(f"/api/rentals/{second}/").data["signature_guarantee"]
        self.assertEqual(guarantee, {"available": False, "minutes": minutes})

    def test_plain_car_has_no_signature_guarantee(self):
        self.car.livery = Car.Livery.NONE
        self.car.save()
        rental_id = self.book()
        guarantee = self.client.get(f"/api/rentals/{rental_id}/").data["signature_guarantee"]
        self.assertFalse(guarantee["available"])

    def test_photos_are_stored_without_exif(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"
        rental_id = self.book()
        self.inspect(rental_id, files=photos(front=image_file(exif=exif)))
        stored = InspectionPhoto.objects.get(angle="front")
        with Image.open(stored.image.path) as image:
            self.assertEqual(len(image.getexif()), 0)

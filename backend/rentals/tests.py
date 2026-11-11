import urllib.error
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ValidationError as ModelValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.factories import make_driver
from cars.models import Car, Feature, Tariff

from .models import Rental
from .services import best_trip_price, calculate_trip_cost, free_waiting_minutes_for

MINUTE, HOUR, DAY = Decimal("0.37"), Decimal("15.90"), Decimal("89.00")
NEAR_CAR = (53.9213, 27.5817)
CLIENT = (53.9180, 27.5790)  # ~420 м до машины


class BestTripPriceTests(APITestCase):
    def test_short_trip_is_billed_per_minute(self):
        self.assertEqual(best_trip_price(10, MINUTE, HOUR, DAY), Decimal("3.70"))

    def test_hour_package_applies_when_cheaper(self):
        self.assertEqual(best_trip_price(50, MINUTE, HOUR, DAY), HOUR)

    def test_extra_minutes_after_full_hour(self):
        self.assertEqual(best_trip_price(61, MINUTE, HOUR, DAY), Decimal("16.27"))

    def test_day_package_with_remaining_hours(self):
        # 26 часов: сутки + два часовых пакета дешевле, чем 26 часов по отдельности.
        self.assertEqual(best_trip_price(26 * 60, MINUTE, HOUR, DAY), Decimal("120.80"))


class FreeWaitingRuleTests(APITestCase):
    def test_examples_from_the_rule(self):
        cases = [((120, 0), 10), ((420, 0), 13), ((900, 0), 23), ((1200, 0), 25), ((420, 3), 18), ((1800, 3), 30)]
        for (walk_seconds, level), expected in cases:
            with self.subTest(walk=walk_seconds, level=level):
                self.assertEqual(free_waiting_minutes_for(walk_seconds, level), expected)

    def test_without_walk_falls_back_to_default(self):
        self.assertEqual(free_waiting_minutes_for(None), 10)


@override_settings(FREE_WAITING_MINUTES=10, INSPECTIONS_REQUIRED=False, TRIP_FACE_CHECK_REQUIRED=False)
class RentalFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.tariff = Tariff.objects.create(
            name="Комфорт",
            price_per_minute=Decimal("0.37"),
            waiting_price_per_minute=Decimal("0.17"),
        )
        self.car = Car.objects.create(
            brand="Geely",
            model="Emgrand",
            year=2023,
            license_plate="8743 AB-7",
            tariff=self.tariff,
            car_class=Car.CarClass.COMFORT,
            latitude=NEAR_CAR[0],
            longitude=NEAR_CAR[1],
        )
        self.car.features.add(Feature.objects.create(name="Подогрев сидений"))
        self.user = make_driver("client")
        self.client.force_authenticate(self.user)

    def book(self, **extra):
        response = self.client.post("/api/rentals/", {"car": self.car.id, **extra}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def shift_reservation(self, rental_id, minutes):
        # Середина минуты: миллисекунды между сдвигом и запросом не перескочат границу округления.
        Rental.objects.filter(pk=rental_id).update(
            reserved_at=timezone.now() - timedelta(minutes=minutes, seconds=-30)
        )

    def test_registration_returns_tokens(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("register"),
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "password": "StrongPass123",
                "password_confirm": "StrongPass123",
                "first_name": "Иван",
                "last_name": "Иванов",
                "phone_number": "+375291112233",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data)

    def test_catalog_is_public_and_includes_features(self):
        self.client.force_authenticate(None)
        response = self.client.get("/api/cars/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["features"], ["Подогрев сидений"])

    def test_full_rental_cycle(self):
        rental_id = self.book()
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Car.Status.RESERVED)

        self.assertEqual(self.client.post(f"/api/rentals/{rental_id}/start/").status_code, 200)
        finish = self.client.post(f"/api/rentals/{rental_id}/finish/")
        self.assertEqual(finish.status_code, 200)

        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Car.Status.AVAILABLE)
        self.assertEqual(Decimal(finish.data["total_cost"]), Decimal("0.37"))

    def test_finish_ignores_client_coordinates(self):
        rental_id = self.book()
        self.client.post(f"/api/rentals/{rental_id}/start/")
        finish = self.client.post(
            f"/api/rentals/{rental_id}/finish/", {"latitude": 95, "longitude": 200}, format="json"
        )
        self.assertEqual(finish.status_code, 200)
        self.assertEqual((finish.data["end_latitude"], finish.data["end_longitude"]), NEAR_CAR)
        self.car.refresh_from_db()
        self.assertEqual((self.car.latitude, self.car.longitude), NEAR_CAR)

    def test_car_coordinates_are_validated(self):
        self.car.latitude = 95
        with self.assertRaises(ModelValidationError):
            self.car.full_clean()
        self.car.latitude, self.car.longitude = NEAR_CAR[0], 181
        with self.assertRaises(ModelValidationError):
            self.car.full_clean()

    def test_trip_cost_is_rounded_up_to_whole_minutes(self):
        started = timezone.now()
        rental = Rental(
            price_per_minute_at_booking=Decimal("0.37"),
            started_at=started,
            finished_at=started + timedelta(seconds=605),
        )
        self.assertEqual(calculate_trip_cost(rental), Decimal("4.07"))

    def test_signature_compensation_reduces_bill(self):
        started = timezone.now()
        rental = Rental(
            price_per_minute_at_booking=Decimal("0.37"),
            compensation_minutes=15,
            started_at=started,
            finished_at=started + timedelta(minutes=40),
        )
        self.assertEqual(calculate_trip_cost(rental), Decimal("9.25"))
        rental.finished_at = started + timedelta(minutes=10)
        self.assertEqual(calculate_trip_cost(rental), Decimal("0.00"))

    def test_waiting_is_free_within_free_window(self):
        rental_id = self.book()
        self.shift_reservation(rental_id, 7)
        response = self.client.post(f"/api/rentals/{rental_id}/start/")
        self.assertEqual(Decimal(response.data["waiting_cost"]), Decimal("0.00"))

    def test_waiting_after_free_window_is_charged(self):
        rental_id = self.book()
        self.shift_reservation(rental_id, 15)
        self.client.post(f"/api/rentals/{rental_id}/start/")
        finish = self.client.post(f"/api/rentals/{rental_id}/finish/")

        self.assertEqual(Decimal(finish.data["waiting_cost"]), Decimal("0.85"))
        self.assertEqual(Decimal(finish.data["trip_cost"]), Decimal("0.37"))
        self.assertEqual(Decimal(finish.data["total_cost"]), Decimal("1.22"))

    def test_cancel_after_free_window_charges_waiting(self):
        rental_id = self.book()
        self.shift_reservation(rental_id, 12)
        response = self.client.post(f"/api/rentals/{rental_id}/cancel/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["total_cost"]), Decimal("0.34"))
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Car.Status.AVAILABLE)

    def test_fair_booking_uses_walking_route(self):
        table = {"code": "Ok", "durations": [[0, 420]], "distances": [[0, 520]]}
        with mock.patch("cars.walking._osrm_get", return_value=table):
            rental_id = self.book(lat=CLIENT[0], lng=CLIENT[1])
        rental = Rental.objects.get(pk=rental_id)
        self.assertEqual(rental.free_waiting_minutes, 13)
        self.assertEqual(rental.walk_duration_s, 420)
        self.assertEqual(rental.walk_source, "osrm")
        self.assertEqual(rental.free_waiting_until, rental.reserved_at + timedelta(minutes=13))

        # Индивидуальное окно 13 минут: 12 минут ожидания — бесплатно, 14 — одна платная.
        self.shift_reservation(rental_id, 12)
        start = self.client.post(f"/api/rentals/{rental_id}/start/")
        self.assertEqual(Decimal(start.data["waiting_cost"]), Decimal("0.00"))

    def test_fair_booking_with_routing_down_uses_estimate(self):
        with mock.patch("cars.walking._osrm_get", side_effect=urllib.error.URLError("offline")):
            rental_id = self.book(lat=CLIENT[0], lng=CLIENT[1])
        rental = Rental.objects.get(pk=rental_id)
        self.assertEqual(rental.walk_source, "estimate")
        self.assertGreaterEqual(rental.free_waiting_minutes, 10)

    def test_far_client_gets_default_window(self):
        rental_id = self.book(lat=53.80, lng=27.40)  # больше 3 км — подмена геопозиции не поможет
        self.assertEqual(Rental.objects.get(pk=rental_id).free_waiting_minutes, 10)

    def test_car_missing_cancels_for_free_and_offers_alternative(self):
        other = Car.objects.create(
            brand="Kia", model="Rio", year=2021, license_plate="2914 IB-7", tariff=self.tariff,
            car_class=Car.CarClass.ECONOMY, latitude=53.9230, longitude=27.5830,
        )
        rental_id = self.book()
        self.shift_reservation(rental_id, 20)  # даже после бесплатного окна — без оплаты
        with mock.patch("cars.walking._osrm_get", side_effect=urllib.error.URLError("offline")):
            response = self.client.post(
                f"/api/rentals/{rental_id}/car-missing/", {"lat": 53.9214, "lng": 27.5818}, format="json"
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data["rental"]["total_cost"]), Decimal("0.00"))
        self.assertEqual(response.data["rental"]["cancel_reason"], "car_missing")
        self.assertEqual(response.data["alternative"]["id"], other.id)
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Car.Status.MAINTENANCE)

    def test_car_missing_alternative_follows_booking_rules(self):
        far = Car.objects.create(
            brand="Kia", model="Rio", year=2021, license_plate="2914 IB-7", tariff=self.tariff,
            car_class=Car.CarClass.COMFORT, latitude=53.95, longitude=27.65,  # ~5,5 км от клиента
        )
        rental_id = self.book()
        table = {"code": "Ok", "durations": [[0, 1800]], "distances": [[0, 6000]]}
        with mock.patch("cars.walking._osrm_get", return_value=table):
            response = self.client.post(
                f"/api/rentals/{rental_id}/car-missing/", {"lat": 53.9214, "lng": 27.5818}, format="json"
            )
        alternative = response.data["alternative"]
        self.assertEqual(alternative["id"], far.id)
        # Бронь отсюда дала бы стандартное окно — обещаем столько же, а не 25 минут.
        self.assertEqual(alternative["free_booking_minutes"], 10)
        self.assertTrue(alternative["eligibility"]["allowed"])

    def test_car_missing_requires_being_near_the_car(self):
        rental_id = self.book()
        response = self.client.post(
            f"/api/rentals/{rental_id}/car-missing/", {"lat": 53.90, "lng": 27.55}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "too_far")

    def test_car_missing_daily_limit(self):
        for _ in range(2):
            Rental.objects.create(
                user=self.user, car=self.car, status=Rental.Status.CANCELLED,
                cancel_reason=Rental.CancelReason.CAR_MISSING, price_per_minute_at_booking=Decimal("0.37"),
            )
        rental_id = self.book()
        response = self.client.post(
            f"/api/rentals/{rental_id}/car-missing/", {"lat": NEAR_CAR[0], "lng": NEAR_CAR[1]}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "limit")

    def test_cannot_book_car_taken_by_another_user(self):
        self.book()
        self.client.force_authenticate(make_driver("other"))
        response = self.client.post("/api/rentals/", {"car": self.car.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_cannot_finish_rental_that_was_not_started(self):
        rental_id = self.book()
        response = self.client.post(f"/api/rentals/{rental_id}/finish/")
        self.assertEqual(response.status_code, 400)

    def test_client_does_not_see_other_users_rentals(self):
        self.book()
        self.client.force_authenticate(make_driver("other"))
        response = self.client.get("/api/rentals/")
        self.assertEqual(response.data["count"], 0)

    def test_staff_trip_list_shows_only_own_rentals(self):
        rental_id = self.book()
        self.client.force_authenticate(make_driver("operator", is_staff=True))
        self.assertEqual(self.client.get("/api/rentals/").data["count"], 0)
        # Карточку чужой аренды сотрудник по-прежнему открывает.
        self.assertEqual(self.client.get(f"/api/rentals/{rental_id}/").status_code, 200)

    @override_settings(INSPECTIONS_REQUIRED=True)
    def test_start_requires_inspection(self):
        rental_id = self.book()
        response = self.client.post(f"/api/rentals/{rental_id}/start/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "inspection_required")

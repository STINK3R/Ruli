import urllib.error
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.factories import make_driver
from rentals.models import Rental

from .models import Car, Tariff
from .walking import estimate_walk

ORIGIN = (53.9023, 27.5619)  # площадь Независимости


class WalkingCatalogTests(APITestCase):
    def setUp(self):
        cache.clear()
        tariff = Tariff.objects.create(name="Комфорт", price_per_minute=Decimal("0.37"))
        common = dict(year=2023, tariff=tariff, brand="Geely")
        self.far = Car.objects.create(
            model="Far", license_plate="1000 AA-7", latitude=53.95, longitude=27.60, **common
        )
        self.near = Car.objects.create(
            model="Near", license_plate="2000 AA-7", latitude=53.903, longitude=27.563, **common
        )

    def osrm_table(self, durations, distances):
        return {"code": "Ok", "durations": [[0, *durations]], "distances": [[0, *distances]]}

    def test_without_coordinates_walk_is_empty(self):
        response = self.client.get("/api/cars/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(car["walk"] is None for car in response.data["results"]))

    def test_cars_are_sorted_by_walking_time(self):
        # Порядок в БД: far, near — OSRM говорит, что near ближе.
        cars = list(Car.objects.order_by("id"))
        durations = [1800 if car == self.far else 240 for car in cars]
        with mock.patch(
            "cars.walking._osrm_get", return_value=self.osrm_table(durations, [2000, 300])
        ):
            response = self.client.get("/api/cars/", {"lat": ORIGIN[0], "lng": ORIGIN[1]})

        results = response.data["results"]
        self.assertEqual([car["model"] for car in results], ["Near", "Far"])
        self.assertEqual(results[0]["walk"]["duration_s"], 240)
        self.assertEqual(results[0]["walk"]["source"], "osrm")

    def test_falls_back_to_estimate_when_routing_is_down(self):
        with mock.patch("cars.walking._osrm_get", side_effect=urllib.error.URLError("offline")):
            response = self.client.get("/api/cars/", {"lat": ORIGIN[0], "lng": ORIGIN[1]})

        results = response.data["results"]
        self.assertEqual(results[0]["model"], "Near")
        self.assertEqual(results[0]["walk"]["source"], "estimate")
        self.assertGreater(results[1]["walk"]["duration_s"], results[0]["walk"]["duration_s"])

    def test_explicit_ordering_wins_over_walking_sort(self):
        Car.objects.filter(pk=self.near.pk).update(year=2019)
        params = {"lat": ORIGIN[0], "lng": ORIGIN[1]}
        with mock.patch("cars.walking._osrm_get", side_effect=urllib.error.URLError("offline")):
            newest_first = self.client.get("/api/cars/", {**params, "ordering": "-year"})
            oldest_first = self.client.get("/api/cars/", {**params, "ordering": "year"})
        # Ближайшая машина (Near, 2019) уходит вниз, если явно попросили сначала новые.
        self.assertEqual([car["model"] for car in newest_first.data["results"]], ["Far", "Near"])
        self.assertEqual([car["model"] for car in oldest_first.data["results"]], ["Near", "Far"])

    @override_settings(FREE_WAITING_MINUTES=10)
    def test_far_origin_is_promised_only_the_standard_window(self):
        # Near — в 100 м (600 с пешком), Far — в ~5,7 км: бронь оттуда даёт стандартное окно.
        cars = list(Car.objects.all())  # порядок, в котором каталог передаёт машины в OSRM
        durations = [1800 if car == self.far else 600 for car in cars]
        distances = [7000 if car == self.far else 700 for car in cars]
        params = {"lat": ORIGIN[0], "lng": ORIGIN[1]}

        def minutes():
            with mock.patch("cars.walking._osrm_get", return_value=self.osrm_table(durations, distances)):
                results = self.client.get("/api/cars/", params).data["results"]
            return {car["model"]: car["free_booking_minutes"] for car in results}

        self.assertEqual(minutes(), {"Near": 16, "Far": 10})

        plus = make_driver("plus")
        for _ in range(settings.PLUS_LEVEL_TRIPS):
            Rental.objects.create(
                user=plus, car=self.near, status=Rental.Status.COMPLETED,
                finished_at=timezone.now(), price_per_minute_at_booking=Decimal("0.37"),
            )
        self.client.force_authenticate(plus)
        self.assertEqual(minutes(), {"Near": 21, "Far": 15})

    def test_route_returns_geometry(self):
        route = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 310.4,
                    "duration": 250.2,
                    "geometry": {"coordinates": [[27.5619, 53.9023], [27.563, 53.903]]},
                }
            ],
        }
        with mock.patch("cars.walking._osrm_get", return_value=route):
            response = self.client.get(
                f"/api/cars/{self.near.id}/route/", {"lat": ORIGIN[0], "lng": ORIGIN[1]}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["duration_s"], 250)
        # OSRM-линия + достроенные отрезки до реальных точек клиента и машины.
        self.assertEqual(len(response.data["geometry"]), 4)

    def test_route_without_coordinates_is_rejected(self):
        response = self.client.get(f"/api/cars/{self.near.id}/route/")
        self.assertEqual(response.status_code, 400)

    def test_route_too_far_is_rejected(self):
        response = self.client.get(f"/api/cars/{self.near.id}/route/", {"lat": 55.75, "lng": 37.61})
        self.assertEqual(response.status_code, 400)

    def test_estimate_is_reasonable_for_a_kilometre(self):
        # ~1 км по прямой → ~1,3 км по улицам → около 17 минут пешком.
        walk = estimate_walk((53.90, 27.56), (53.909, 27.56))
        self.assertTrue(15 * 60 <= walk["duration_s"] <= 20 * 60)


class TripPlannerTests(APITestCase):
    """«Куда едем?»: ближайшая машина не всегда выгоднее."""

    def setUp(self):
        cache.clear()
        cheap = Tariff.objects.create(name="Эконом", price_per_minute=Decimal("0.29"), waiting_price_per_minute=Decimal("0.10"))
        dear = Tariff.objects.create(name="Премиум", price_per_minute=Decimal("0.95"), waiting_price_per_minute=Decimal("0.30"))
        self.premium = Car.objects.create(
            brand="BMW", model="3", year=2024, license_plate="3000 AA-7", car_class="premium",
            tariff=dear, latitude=53.9026, longitude=27.5625,
        )
        self.economy = Car.objects.create(
            brand="Kia", model="Rio", year=2023, license_plate="4000 AA-7", car_class="economy",
            tariff=cheap, latitude=53.9050, longitude=27.5660,
        )
        self.params = {"lat": ORIGIN[0], "lng": ORIGIN[1], "to_lat": 53.93, "to_lng": 27.65}

    def plan(self, **params):
        offline = urllib.error.URLError("offline")
        with mock.patch("cars.walking._osrm_get", side_effect=offline), \
                mock.patch("cars.driving._osrm_get", side_effect=offline):
            return self.client.get("/api/cars/plan/", {**self.params, **params})

    def test_cheapest_option_is_not_the_nearest(self):
        response = self.plan()
        self.assertEqual(response.status_code, 200, response.data)
        options = response.data["options"]
        self.assertEqual(options[0]["car"]["id"], self.economy.id)
        self.assertIn("cheapest", options[0]["badges"])
        nearest = next(o for o in options if "nearest" in o["badges"])
        self.assertEqual(nearest["car"]["id"], self.premium.id)
        self.assertGreater(Decimal(response.data["saving_vs_nearest"]), 0)
        self.assertEqual(options[0]["trip_cost"], Decimal(options[0]["trip_minutes"]) * Decimal("0.29"))
        self.assertGreater(len(response.data["route"]["geometry"]), 1)

    def test_driver_sees_only_classes_open_to_them(self):
        novice = make_driver("novice", dob=timezone.localdate().replace(year=timezone.localdate().year - 19))
        self.client.force_authenticate(novice)
        ids = {option["car"]["id"] for option in self.plan().data["options"]}
        self.assertEqual(ids, {self.economy.id})

    def test_both_points_are_required(self):
        response = self.client.get("/api/cars/plan/", {"lat": ORIGIN[0], "lng": ORIGIN[1]})
        self.assertEqual(response.status_code, 400)

    def test_hour_package_is_named(self):
        from .planner import price_with_label

        tariff = Tariff(price_per_minute=Decimal("0.37"), price_per_hour=Decimal("15.90"))
        self.assertEqual(price_with_label(10, tariff), (Decimal("3.70"), "поминутно"))
        self.assertEqual(price_with_label(55, tariff), (Decimal("15.90"), "пакет «Час»"))


class GeocodeTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_search_results_are_trimmed_to_address(self):
        payload = [{
            "lat": "53.9", "lon": "27.56", "name": "ТЦ Галерея",
            "address": {"road": "проспект Победителей", "house_number": "9", "suburb": "Центральный район"},
        }]
        with mock.patch("cars.geocoding._get", return_value=payload):
            response = self.client.get("/api/geocode/", {"q": "Галерея"})
        self.assertEqual(response.data[0]["title"], "ТЦ Галерея · проспект Победителей, 9")
        self.assertEqual(response.data[0]["subtitle"], "Центральный район")

    def test_offline_geocoder_returns_point_label(self):
        with mock.patch("cars.geocoding._get", side_effect=urllib.error.URLError("offline")):
            response = self.client.get("/api/geocode/", {"lat": 53.91, "lng": 27.55})
        self.assertEqual(response.data["title"], "Точка на карте")

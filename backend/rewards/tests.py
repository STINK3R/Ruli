from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.factories import make_driver
from accounts.models import User
from cars.models import Car, Tariff
from rentals.models import Rental

from . import services
from .catalog import rank_for
from .models import PointsEntry, Referral


@override_settings(INSPECTIONS_REQUIRED=False, TRIP_FACE_CHECK_REQUIRED=False)
class TripRewardsTests(APITestCase):
    def setUp(self):
        cache.clear()
        tariff = Tariff.objects.create(name="Эконом", price_per_minute=Decimal("0.30"))
        self.car = Car.objects.create(
            brand="Kia", model="Rio", year=2023, license_plate="1111 AA-7", car_class="economy",
            tariff=tariff, latitude=53.9, longitude=27.56,
        )
        self.driver = make_driver("rider")
        self.client.force_authenticate(self.driver)

    def ride(self, minutes=20, use_points=False, started_hour=None):
        rental = self.client.post("/api/rentals/", {"car": self.car.id}, format="json").data
        self.client.post(f"/api/rentals/{rental['id']}/start/")
        started = timezone.now() - timedelta(minutes=minutes)
        if started_hour is not None:
            # Вчера в заданный час: поездка гарантированно в прошлом.
            started = timezone.localtime(timezone.now() - timedelta(days=1)).replace(hour=started_hour, minute=0)
        Rental.objects.filter(pk=rental["id"]).update(started_at=started)
        return self.client.post(f"/api/rentals/{rental['id']}/finish/", {"use_points": use_points}, format="json")

    def test_finished_trip_gives_points_and_first_achievement(self):
        response = self.ride(minutes=20)
        self.assertEqual(response.status_code, 200, response.data)
        titles = [item["title"] for item in response.data["rewards"]]
        self.assertIn("Достижение «Первый тег»", titles)
        trip = PointsEntry.objects.get(user=self.driver, kind=PointsEntry.Kind.TRIP)
        self.assertEqual(trip.amount, 10 + 20 // 2)

    def test_achievement_is_given_once(self):
        self.ride()
        self.car.status = Car.Status.AVAILABLE
        self.car.save()
        self.ride()
        self.assertEqual(PointsEntry.objects.filter(user=self.driver, key="ach:first_trip").count(), 1)

    def test_night_ride_and_long_haul(self):
        self.ride(minutes=70, started_hour=23)
        keys = set(PointsEntry.objects.filter(user=self.driver).values_list("key", flat=True))
        self.assertIn("ach:night_rider", keys)
        self.assertIn("ach:long_haul", keys)

    def test_points_pay_up_to_30_percent(self):
        services.grant(self.driver, 5000, PointsEntry.Kind.BONUS, "Подарок")
        response = self.ride(minutes=40, use_points=True)
        # Баллами — ровно 30% полной цены (40–41 мин × 0,30 BYN), 1 балл = 0,01 BYN.
        discount = Decimal(response.data["points_discount"])
        full = Decimal(response.data["total_cost"]) + discount
        self.assertEqual(response.data["points_spent"], int(full * 30))
        self.assertEqual(discount, Decimal(response.data["points_spent"]) / 100)
        self.assertEqual(Decimal(response.data["total_cost"]), full - discount)
        # В чеке «Поездка» — полная цена, скидка — отдельной строкой.
        self.assertEqual(Decimal(response.data["trip_cost"]), full)

    def test_without_flag_points_are_kept(self):
        services.grant(self.driver, 500, PointsEntry.Kind.BONUS, "Подарок")
        response = self.ride(minutes=10)
        self.assertEqual(response.data["points_spent"], 0)
        self.assertGreater(services.balance(self.driver), 500)

    def test_weekly_quest_completes(self):
        for _ in range(3):
            self.car.refresh_from_db()
            self.car.status = Car.Status.AVAILABLE
            self.car.save()
            self.ride(minutes=25)
        quests = {quest["code"]: quest for quest in services.quest_progress(self.driver)}
        self.assertTrue(quests["trips_3"]["done"])
        self.assertTrue(quests["minutes_60"]["done"])


class ReferralTests(APITestCase):
    def test_code_round_trip(self):
        user = make_driver("host")
        code = services.referral_code(user)
        self.assertTrue(code.startswith("RULI-"))
        self.assertEqual(services.user_by_code(code), user)
        self.assertEqual(services.user_by_code(code.lower()), user)
        self.assertIsNone(services.user_by_code("RULI-0000"))

    def test_register_with_code_links_friend(self):
        host = make_driver("host")
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "friend", "email": "friend@example.com", "password": "StrongPass123",
                "password_confirm": "StrongPass123", "first_name": "Друг", "last_name": "Новый",
                "phone_number": "+375295550123", "ref": services.referral_code(host),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Referral.objects.filter(referrer=host, referee__username="friend").exists())

    def test_wrong_code_is_rejected(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "friend", "email": "friend@example.com", "password": "StrongPass123",
                "password_confirm": "StrongPass123", "first_name": "Друг", "last_name": "Новый",
                "phone_number": "+375295550123", "ref": "RULI-ZZZZ",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("ref", response.data)

    def test_both_get_points_after_first_trip(self):
        host = make_driver("host")
        friend = make_driver("friend")
        Referral.objects.create(referrer=host, referee=friend)
        services.reward_referral(friend)
        self.assertEqual(services.balance(friend), 150)
        self.assertEqual(services.balance(host), 150)
        self.assertEqual(services.reward_referral(friend), [])  # второй раз — ничего


class LeaderboardTests(APITestCase):
    def test_top_and_my_place(self):
        users = [make_driver(f"user{i}", first_name=f"Имя{i}", last_name="Фамилия") for i in range(3)]
        for user, amount in zip(users, (50, 300, 120)):
            services.grant(user, amount, PointsEntry.Kind.BONUS, "Бонус")
        services.grant(users[1], -200, PointsEntry.Kind.SPEND, "Скидка")  # траты не снижают место
        self.client.force_authenticate(users[0])
        data = self.client.get("/api/rewards/leaderboard/", {"period": "week"}).data
        self.assertEqual([row["score"] for row in data["top"]], [300, 120, 50])
        self.assertEqual(data["top"][0]["name"], "Имя1 Ф.")
        self.assertEqual(data["me"]["place"], 3)
        self.assertTrue(data["top"][2]["me"])

    def test_old_points_are_not_in_this_week(self):
        user = make_driver("old")
        entry = services.grant(user, 100, PointsEntry.Kind.BONUS, "Давно")
        PointsEntry.objects.filter(pk=entry.pk).update(created_at=timezone.now() - timedelta(days=20))
        self.assertEqual(self.client.get("/api/rewards/leaderboard/").data["total"], 0)
        self.assertEqual(self.client.get("/api/rewards/leaderboard/", {"period": "all"}).data["total"], 1)

    def test_ranks(self):
        self.assertEqual(rank_for(0)[0][1], "Той")
        self.assertEqual(rank_for(850)[0][1], "Бомбер")
        self.assertEqual(rank_for(850)[1][1], "Кинг")
        self.assertIsNone(rank_for(10_000)[1])


class SummaryTests(APITestCase):
    def test_summary_and_verified_achievement(self):
        user = User.objects.create_user("plain", "plain@example.com", "StrongPass123")
        self.client.force_authenticate(user)
        data = self.client.get("/api/rewards/").data
        self.assertEqual(data["balance"], 0)
        self.assertEqual(data["rank"]["title"], "Той")
        self.assertEqual(len(data["quests"]), 4)
        services.on_verified(user)
        unlocked = {a["code"] for a in self.client.get("/api/rewards/").data["achievements"] if a["unlocked"]}
        self.assertEqual(unlocked, {"verified"})

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/rewards/").status_code, 401)


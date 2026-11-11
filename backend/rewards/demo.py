"""Демо для «Движа»: баллы за уже существующие поездки и соперники в рейтинге."""

import random
from datetime import timedelta

from django.utils import timezone

from accounts.models import User, VerificationStatus

from . import services
from .models import PointsEntry

RIDERS = [
    ("Мария", "Ковалёва"), ("Дмитрий", "Жук"), ("Анна", "Шарко"), ("Павел", "Лис"),
    ("Ольга", "Бондарь"), ("Никита", "Мороз"), ("Елена", "Сокол"), ("Артём", "Гуд"), ("Вика", "Рыбак"),
]
SEED_KEY = "seed:riders:v2"
TITLES = ["Поездка на Kia Rio", "Поездка на Geely Coolray", "Задание «3 поездки за неделю»",
          "Достижение «Ночной райдер»", "Поездка на Skoda Rapid", "Задание «60 минут за рулём»"]


def backfill():
    """Начисления за поездки, которые были до появления «Движа» (повтор ничего не задвоит)."""
    from rentals.models import Rental

    for user in User.objects.filter(verification_status=VerificationStatus.APPROVED):
        services.on_verified(user)
    for rental in Rental.objects.filter(status=Rental.Status.COMPLETED).select_related("car", "user").order_by("finished_at"):
        services.on_trip_finished(rental)


def ensure_riders(stdout=None):
    """Соперники в рейтинге: без пароля, войти под ними нельзя."""
    now = timezone.now()
    for index, (first, last) in enumerate(RIDERS):
        username = f"rider{index + 1}"
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User(username=username, email=f"{username}@ruli.by", first_name=first, last_name=last)
            user.set_unusable_password()
            user.save()
        # Метка версии демо-данных: при её смене соперники пересоздаются.
        if user.points.filter(key=SEED_KEY).exists():
            continue
        user.points.all().delete()
        PointsEntry.objects.create(user=user, amount=50, kind=PointsEntry.Kind.BONUS, title="Бонус новичка", key=SEED_KEY)
        rng = random.Random(index * 31 + 7)
        heat = 1.6 - index * 0.12  # первые в списке — самые активные
        for _ in range(rng.randint(8, 18)):
            entry = PointsEntry.objects.create(
                user=user, amount=round(rng.choice([12, 18, 25, 30, 40, 50, 60]) * heat), kind=PointsEntry.Kind.TRIP,
                title=rng.choice(TITLES),
            )
            # Часть баллов — за последние дни, часть — раньше: рейтинги 7 и 30 дней различаются.
            PointsEntry.objects.filter(pk=entry.pk).update(created_at=now - timedelta(days=rng.uniform(0, 24)))
    if stdout:
        stdout.write(f"Рейтинг «Движа»: {len(RIDERS)} соперников.")


def seed_rewards(stdout=None):
    backfill()
    ensure_riders(stdout)

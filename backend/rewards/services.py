"""Начисление и списание баллов, задания недели, рейтинг и коды «Приведи друга»."""

from datetime import datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .catalog import (
    ACHIEVEMENTS,
    ACHIEVEMENTS_BY_CODE,
    MAX_DISCOUNT_SHARE,
    POINT_VALUE_BYN,
    QUESTS,
    REFERRAL_POINTS,
    TRIP_BASE_POINTS,
    TRIP_MAX_MINUTE_POINTS,
    TRIP_POINTS_PER_MINUTES,
    rank_for,
)
from .models import PointsEntry, Referral

K = PointsEntry.Kind
POINT = Decimal(POINT_VALUE_BYN)
CODE_SALT = 7919
CODE_SHIFT = 104_729
DIGITS = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # без I и O — не путаются с 1 и 0


# ---------- Баланс ----------

def balance(user):
    return user.points.aggregate(total=Sum("amount"))["total"] or 0


def earned_total(user):
    return user.points.filter(amount__gt=0).aggregate(total=Sum("amount"))["total"] or 0


def grant(user, amount, kind, title, key=None, rental=None):
    """Начислить баллы. С ключом — не больше одного раза (повтор вернёт None)."""
    if key and user.points.filter(key=key).exists():
        return None
    try:
        with transaction.atomic():
            return PointsEntry.objects.create(
                user=user, amount=amount, kind=kind, title=title, key=key, rental=rental
            )
    except IntegrityError:  # одновременный запрос успел первым
        return None


def grant_achievement(user, code, rental=None):
    item = ACHIEVEMENTS_BY_CODE[code]
    return grant(user, item.points, K.ACHIEVEMENT, f"Достижение «{item.title}»", key=f"ach:{code}", rental=rental)


def unlocked_codes(user):
    keys = user.points.filter(key__startswith="ach:").values_list("key", flat=True)
    return {key.split(":", 1)[1] for key in keys}


# ---------- Неделя и задания ----------

def week_start(now=None):
    local = timezone.localtime(now or timezone.now())
    monday = local.date() - timedelta(days=local.weekday())
    return timezone.make_aware(datetime.combine(monday, time.min), local.tzinfo)


def _completed(user):
    from rentals.models import Rental

    return Rental.objects.filter(user=user, status=Rental.Status.COMPLETED).select_related("car")


def _is_night(moment):
    hour = timezone.localtime(moment).hour
    return hour >= 22 or hour < 5


def quest_progress(user, now=None):
    start = week_start(now)
    trips = list(_completed(user).filter(finished_at__gte=start))
    values = {
        "trips_3": len(trips),
        "minutes_60": sum(trip.duration_minutes or 0 for trip in trips),
        "night": sum(1 for trip in trips if trip.started_at and _is_night(trip.started_at)),
        "signature": sum(1 for trip in trips if trip.car.is_signature),
    }
    week = start.date().isoformat()
    done = set(user.points.filter(key__startswith="quest:", key__endswith=f":{week}").values_list("key", flat=True))
    return [
        {
            "code": quest.code,
            "title": quest.title,
            "target": quest.target,
            "unit": quest.unit,
            "points": quest.points,
            "progress": min(values[quest.code], quest.target),
            "done": f"quest:{quest.code}:{week}" in done,
        }
        for quest in QUESTS
    ]


# ---------- События ----------

def trip_points(rental):
    minutes = rental.duration_minutes or 0
    return TRIP_BASE_POINTS + min(TRIP_MAX_MINUTE_POINTS, minutes // TRIP_POINTS_PER_MINUTES)


def on_trip_finished(rental):
    """Всё, что даёт завершённая поездка: баллы, достижения, задания недели, награда за друга."""
    from inspections.models import Damage, Inspection

    user = rental.user
    awarded = [grant(user, trip_points(rental), K.TRIP, f"Поездка на {rental.car.title}", key=f"trip:{rental.pk}", rental=rental)]

    trips = list(_completed(user))
    count = len(trips)
    checks = {
        "first_trip": count >= 1,
        "trips_5": count >= 5,
        "trips_20": count >= 20,
        "night_rider": bool(rental.started_at and _is_night(rental.started_at)),
        "early_bird": bool(rental.started_at and 5 <= timezone.localtime(rental.started_at).hour < 8),
        "long_haul": (rental.duration_minutes or 0) >= 60,
        "signature": rental.car.is_signature,
        "collector": len({trip.car.car_class for trip in trips}) >= 3,
        "detective": Damage.objects.filter(
            first_seen__rental=rental, first_seen__kind=Inspection.Kind.START
        ).exists(),
    }
    awarded += [grant_achievement(user, code, rental) for code, ok in checks.items() if ok]

    week = week_start().date().isoformat()
    for quest in quest_progress(user):
        if quest["progress"] >= quest["target"] and not quest["done"]:
            awarded.append(
                grant(user, quest["points"], K.QUEST, f"Задание «{quest['title']}»", key=f"quest:{quest['code']}:{week}", rental=rental)
            )

    if count == 1:
        awarded += reward_referral(user, rental)
    return [entry for entry in awarded if entry]


def reward_referral(user, rental=None):
    referral = Referral.objects.filter(referee=user, rewarded_at__isnull=True).select_related("referrer").first()
    if referral is None:
        return []
    referral.rewarded_at = timezone.now()
    referral.save(update_fields=["rewarded_at"])
    friend = user.first_name or user.username
    return [
        grant(user, REFERRAL_POINTS, K.REFERRAL, "Бонус за регистрацию по приглашению", key="ref:welcome", rental=rental),
        grant(referral.referrer, REFERRAL_POINTS, K.REFERRAL, f"{friend} прокатился по твоему коду", key=f"ref:friend:{user.pk}"),
        grant_achievement(referral.referrer, "crew"),
    ]


def on_verified(user):
    return grant_achievement(user, "verified")


# ---------- Скидка баллами ----------

def max_points_for(cost, available):
    """Сколько баллов можно списать: до 30% стоимости поездки и не больше баланса."""
    if cost <= 0 or available <= 0:
        return 0
    limit = (Decimal(cost) * Decimal(MAX_DISCOUNT_SHARE) / POINT).to_integral_value(rounding=ROUND_DOWN)
    return int(min(Decimal(available), limit))


def spend_for_trip(rental, cost):
    """Вызывается внутри транзакции завершения: списывает баллы и возвращает скидку в BYN."""
    user = rental.user
    # Блокируем строку пользователя: две одновременные поездки не потратят одни баллы дважды.
    type(user).objects.select_for_update().filter(pk=user.pk).first()
    points = max_points_for(cost, balance(user))
    if points == 0:
        return 0, Decimal("0.00")
    PointsEntry.objects.create(
        user=user, amount=-points, kind=K.SPEND, title=f"Скидка на поездку #{rental.pk}", rental=rental,
        key=f"spend:{rental.pk}",
    )
    return points, (points * POINT).quantize(Decimal("0.01"))


# ---------- Приведи друга ----------

def _to_base(number):
    text = ""
    while number:
        number, rest = divmod(number, len(DIGITS))
        text = DIGITS[rest] + text
    return text or "0"


def referral_code(user):
    return f"RULI-{_to_base(user.pk * CODE_SALT + CODE_SHIFT)}"


def user_by_code(code):
    from accounts.models import User

    raw = (code or "").strip().upper().replace("RULI-", "").replace("RULI", "")
    if not raw or any(char not in DIGITS for char in raw):
        return None
    number = 0
    for char in raw:
        number = number * len(DIGITS) + DIGITS.index(char)
    pk, rest = divmod(number - CODE_SHIFT, CODE_SALT)
    if rest or pk <= 0:
        return None
    return User.objects.filter(pk=pk).first()


def attach_referral(user, code):
    referrer = user_by_code(code)
    if referrer is None or referrer.pk == user.pk:
        return None
    referral, _ = Referral.objects.get_or_create(referee=user, defaults={"referrer": referrer})
    return referral


# ---------- Рейтинг ----------

def display_name(user):
    """«Алексей Д.» — в общем рейтинге не показываем фамилию целиком."""
    first = user.first_name or user.username
    initial = f" {user.last_name[0]}." if user.last_name else ""
    return f"{first}{initial}"


PERIODS = {"week": 7, "month": 30}


def leaderboard(period="week", me=None, limit=20):
    from accounts.models import User
    from rentals.models import Rental

    # Рейтинг — за скользящие 7 или 30 дней: в понедельник утром он не пустой.
    since = timezone.now() - timedelta(days=PERIODS[period]) if period in PERIODS else None
    filters = Q(points__amount__gt=0)
    trip_filter = Q(rentals__status=Rental.Status.COMPLETED)
    if since:
        filters &= Q(points__created_at__gte=since)
        trip_filter &= Q(rentals__finished_at__gte=since)
    rows = list(
        User.objects.filter(is_active=True)
        .annotate(score=Sum("points__amount", filter=filters))
        .filter(score__gt=0)
        .order_by("-score", "id")
        .values("id", "score")
    )
    place_of = {row["id"]: index + 1 for index, row in enumerate(rows)}
    top_ids = [row["id"] for row in rows[:limit]]
    if me is not None and me.pk in place_of and me.pk not in top_ids:
        top_ids.append(me.pk)
    users = {
        user.pk: user
        for user in User.objects.filter(pk__in=top_ids).annotate(trips=Count("rentals", filter=trip_filter))
    }
    score_of = {row["id"]: row["score"] for row in rows}

    def entry(pk):
        user = users[pk]
        rank, _ = rank_for(earned_total(user))
        return {
            "place": place_of[pk],
            "name": display_name(user),
            "initials": f"{(user.first_name or user.username)[0]}{(user.last_name or ' ')[0]}".strip().upper(),
            "score": score_of[pk],
            "trips": user.trips,
            "rank": rank[1],
            "me": me is not None and pk == me.pk,
        }

    return {
        "period": period,
        "since": since,
        "top": [entry(pk) for pk in top_ids if place_of[pk] <= limit],
        "me": entry(me.pk) if me is not None and me.pk in place_of else None,
        "total": len(rows),
    }


def summary(user):
    earned = earned_total(user)
    current, following = rank_for(earned)
    unlocked = unlocked_codes(user)
    return {
        "balance": balance(user),
        "balance_byn": str((balance(user) * POINT).quantize(Decimal("0.01"))),
        "earned": earned,
        "rank": {"title": current[1], "text": current[2], "from": current[0]},
        "next_rank": {"title": following[1], "from": following[0]} if following else None,
        "achievements": [
            {
                "code": item.code,
                "title": item.title,
                "text": item.text,
                "points": item.points,
                "icon": item.icon,
                "unlocked": item.code in unlocked,
            }
            for item in ACHIEVEMENTS
        ],
        "quests": quest_progress(user),
        "week_ends": week_start() + timedelta(days=7),
        "referral": {
            "code": referral_code(user),
            "points": REFERRAL_POINTS,
            "friends": Referral.objects.filter(referrer=user).count(),
            "rewarded": Referral.objects.filter(referrer=user, rewarded_at__isnull=False).count(),
        },
        "rules": {
            "trip_base": TRIP_BASE_POINTS,
            "per_minutes": TRIP_POINTS_PER_MINUTES,
            "point_value": POINT_VALUE_BYN,
            "max_discount_share": MAX_DISCOUNT_SHARE,
        },
    }

from django.conf import settings
from django.db import models


class PointsEntry(models.Model):
    """Строка журнала баллов. Баланс — сумма всех строк, история никогда не переписывается."""

    class Kind(models.TextChoices):
        TRIP = "trip", "Поездка"
        ACHIEVEMENT = "achievement", "Достижение"
        QUEST = "quest", "Задание недели"
        REFERRAL = "referral", "Приведи друга"
        SPEND = "spend", "Скидка на поездку"
        BONUS = "bonus", "Бонус от Рули"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Пользователь", on_delete=models.CASCADE, related_name="points"
    )
    amount = models.IntegerField("Баллы")
    kind = models.CharField("Тип", max_length=12, choices=Kind.choices)
    title = models.CharField("За что", max_length=120)
    rental = models.ForeignKey(
        "rentals.Rental", verbose_name="Поездка", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="points_entries",
    )
    # Ключ защищает от двойного начисления: одно достижение, одно задание недели на пользователя.
    key = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Баллы"
        verbose_name_plural = "Журнал баллов"
        ordering = ("-created_at", "-id")
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="one_reward_per_key")]

    def __str__(self):
        return f"{self.user}: {self.amount:+d} — {self.title}"


class Referral(models.Model):
    """Друг пришёл по коду. Награда — обоим, когда друг завершит первую поездку."""

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Пригласил", on_delete=models.CASCADE, related_name="referrals"
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="Друг", on_delete=models.CASCADE, related_name="referred_by"
    )
    created_at = models.DateTimeField("Зарегистрировался", auto_now_add=True)
    rewarded_at = models.DateTimeField("Награда начислена", null=True, blank=True)

    class Meta:
        verbose_name = "Приглашение"
        verbose_name_plural = "Приглашения"

    def __str__(self):
        return f"{self.referrer} → {self.referee}"

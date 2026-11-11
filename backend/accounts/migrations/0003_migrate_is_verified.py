from django.db import migrations
from django.utils import timezone

# Ориентиры рынка (Hello, Anytime, Делимобиль, Яндекс Драйв — открытые источники, 10.2026):
# эконом с 18 лет без стажа, комфорт — 19/1, «стиль» — 21/2, премиум — с опытом в сервисе.
CLASS_REQUIREMENTS = [
    ("economy", 18, 0, 0, "Сразу после получения категории B"),
    ("comfort", 19, 1, 0, "Стаж от года — машины мощнее и дороже"),
    ("business", 21, 2, 2, "Стаж от 2 лет и пара поездок в «Рули» без замечаний"),
    ("premium", 23, 3, 5, "Стаж от 3 лет и 5 поездок без замечаний — «Допуск Плюс»"),
]


def forwards(apps, schema_editor):
    ClassRequirement = apps.get_model("accounts", "ClassRequirement")
    User = apps.get_model("accounts", "User")
    DriverVerification = apps.get_model("accounts", "DriverVerification")

    for car_class, age, experience, trips, note in CLASS_REQUIREMENTS:
        ClassRequirement.objects.update_or_create(
            car_class=car_class,
            defaults={
                "min_age": age,
                "min_experience_years": experience,
                "min_completed_rentals": trips,
                "note": note,
            },
        )

    now = timezone.now()
    for user in User.objects.filter(is_verified=True):
        DriverVerification.objects.create(
            user=user,
            status="approved",
            source="legacy",
            full_name_on_document=" ".join(
                part for part in (user.last_name, user.first_name, user.patronymic) if part
            ),
            date_of_birth=user.date_of_birth,
            license_number=user.driver_license_number,
            license_issued_on=user.driver_license_issued,
            submitted_at=now,
            reviewed_at=now,
        )
        user.verification_status = "approved"
        user.driving_since = user.driver_license_issued
        user.save(update_fields=["verification_status", "driving_since"])


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(verification_status="approved").update(is_verified=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_verification")]

    operations = [migrations.RunPython(forwards, backwards)]

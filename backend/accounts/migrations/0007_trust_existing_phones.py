"""Водители, одобренные до появления SMS-кода, не теряют доступ к поездкам.

Их номер проверял модератор вместе с документами — считаем его подтверждённым.
Новые и неподтверждённые пользователи проходят SMS-код как все.
"""

from django.db import migrations
from django.utils import timezone


def trust_approved(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        verification_status="approved", phone_number__isnull=False, phone_verified_at__isnull=True
    ).update(phone_verified_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_strict_kyc")]

    operations = [migrations.RunPython(trust_approved, migrations.RunPython.noop)]

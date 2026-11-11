#!/bin/sh
set -e

if [ -z "${SECRET_KEY:-}" ]; then
    SECRET_KEY_FILE=/run/carsharing-secrets/django-secret-key
    mkdir -p "$(dirname "$SECRET_KEY_FILE")"
    if [ ! -s "$SECRET_KEY_FILE" ]; then
        echo "==> Создание постоянного ключа Django"
        (umask 077 && python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > "$SECRET_KEY_FILE")
    fi
    SECRET_KEY=$(cat "$SECRET_KEY_FILE")
    export SECRET_KEY
fi

echo "==> Ожидание MySQL"
python - <<'PY'
import os
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection
from django.db.utils import OperationalError

for attempt in range(60):
    try:
        connection.ensure_connection()
        print("MySQL доступна")
        break
    except OperationalError as exc:
        print(f"MySQL ещё не готова ({exc.args[0] if exc.args else exc}), попытка {attempt + 1}")
        time.sleep(2)
else:
    raise SystemExit("MySQL так и не стала доступна")
PY

echo "==> Миграции"
python manage.py migrate --noinput
python manage.py createcachetable

echo "==> Удаление сканов документов после срока хранения"
python manage.py purge_verification_files

echo "==> Статика"
python manage.py collectstatic --noinput --verbosity 0

echo "==> Демо-данные"
python manage.py seed_demo

exec "$@"

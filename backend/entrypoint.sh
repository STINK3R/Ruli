#!/bin/sh
set -e

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

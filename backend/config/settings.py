from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, "django-insecure-dev-key-only-for-local-development"),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    # При ручном запуске Django укажите доступную MySQL; Compose задаёт адрес сервиса db.
    DATABASE_URL=(str, "mysql://carsharing:carsharing@127.0.0.1:3306/carsharing"),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost", "http://127.0.0.1"]),
    FREE_WAITING_MINUTES=(int, 10),
    OSRM_FOOT_URL=(str, "https://routing.openstreetmap.de/routed-foot"),
    OSRM_TIMEOUT_SECONDS=(float, 4.0),
    WALK_CACHE_SECONDS=(int, 60),
    PRIVATE_MEDIA_ROOT=(str, ""),
    OSRM_CAR_URL=(str, "https://routing.openstreetmap.de/routed-car"),
    GEOCODER_URL=(str, "https://nominatim.openstreetmap.org"),
    # Учебный стенд: код из SMS показывается в приложении, доступны демо-документы.
    KYC_DEMO_MODE=(bool, True),
    SMS_DEMO_MODE=(bool, True),
    TRIP_FACE_CHECK_REQUIRED=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "accounts",
    "cars",
    "rentals",
    "inspections",
    "rewards",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {})["charset"] = "utf8mb4"

AUTH_USER_MODEL = "accounts.User"

# Общий кэш в БД: у gunicorn несколько процессов, и лимит запросов к OSRM
# (не чаще 1 в секунду), кэш маршрутов и throttling должны быть общими.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Minsk"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Сканы документов водителей: отдельный том, nginx его не раздаёт (см. accounts/storage.py).
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT") or str(BASE_DIR / "private_media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "DEFAULT_THROTTLE_RATES": {
        "verification_upload": "60/hour",
        "car_missing": "10/hour",
        "login": "10/min",
        "register": "5/hour",
        "phone_code": "8/hour",
        "liveness": "30/hour",
        "planner": "60/hour",
    },
    # Перед бэкендом один nginx: он дописывает адрес клиента в конец X-Forwarded-For,
    # лимиты считаются по этому адресу, а не по подставленному клиентом заголовку.
    "NUM_PROXIES": 1,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# Сколько минут бронь держится бесплатно, дальше начисляется ожидание по тарифу.
FREE_WAITING_MINUTES = env("FREE_WAITING_MINUTES")

# Пешеходные маршруты до машин (OSRM, профиль foot). При недоступности —
# оценка по прямой, см. cars/walking.py.
OSRM_FOOT_URL = env("OSRM_FOOT_URL")
OSRM_TIMEOUT_SECONDS = env("OSRM_TIMEOUT_SECONDS")
WALK_CACHE_SECONDS = env("WALK_CACHE_SECONDS")

# «Рули ID»: загрузка документов и согласия по Закону РБ № 99-З «О защите персональных данных».
VERIFICATION_MAX_UPLOAD_MB = 10
VERIFICATION_RETENTION_DAYS = 30
VERIFICATION_SLA_MINUTES = 30
CONSENT_VERSION = "2026-10"
PLUS_LEVEL_TRIPS = 5  # чистых поездок за 180 дней для «Допуска Плюс»

# «Честная бронь»: бесплатное ожидание зависит от пешего пути до машины.
FAIR_BOOKING_MAX_ORIGIN_M = 3000
CAR_MISSING_RADIUS_M = 300
CAR_MISSING_DAILY_LIMIT = 2

# «Паспорт кузова»: акты осмотра обязательны до старта и после поездки.
INSPECTIONS_REQUIRED = True
INSPECTION_MIN_BRIGHTNESS = 40
INSPECTION_MIN_SHARPNESS = 6.0
SIGNATURE_COMPENSATION_MINUTES = 15
DAMAGE_CLAIM_WINDOW_HOURS = 24

# Строгий KYC: телефон по SMS, личный номер, реестр ГАИ (имитация), проверка «живости».
KYC_DEMO_MODE = env("KYC_DEMO_MODE")
SMS_DEMO_MODE = env("SMS_DEMO_MODE")
PHONE_CODE_TTL_SECONDS = 600
PHONE_CODE_RESEND_SECONDS = 60
PHONE_CODE_MAX_ATTEMPTS = 5
LIVENESS_TTL_SECONDS = 120
LIVENESS_VALID_HOURS = 24
LIVENESS_MIN_MOTION = 4.0  # средняя разница кадров (0–255): фото, поднесённое к камере, почти не меняется
# Перед стартом поездки — короткая проверка лица: за руль садится владелец аккаунта.
TRIP_FACE_CHECK_REQUIRED = env("TRIP_FACE_CHECK_REQUIRED")

# Планировщик «Куда едем?»: время в пути на машине и поиск адреса.
OSRM_CAR_URL = env("OSRM_CAR_URL")
GEOCODER_URL = env("GEOCODER_URL")
TRAFFIC_FACTOR = 1.25  # OSRM не знает пробок — закладываем запас
PARKING_MINUTES = 3  # найти место и закрыть машину
PLANNER_CANDIDATES = 6

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"ruli": {"handlers": ["console"], "level": "INFO"}},
}

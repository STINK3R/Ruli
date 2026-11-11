"""Пешеходная доступность автомобилей: время и маршрут от клиента до машины.

Основной источник — OSRM с пешеходным профилем (по умолчанию публичный сервер
FOSSGIS, тот же, что использует openstreetmap.org). Если сервис недоступен,
время оценивается по расстоянию по прямой с коэффициентом извилистости улиц,
поэтому сортировка и карточки работают и без интернета.
"""

import hashlib
import json
import math
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache

WALK_SPEED_MPS = 1.25  # ~4,5 км/ч — средний темп пешехода в городе
DETOUR_FACTOR = 1.3  # улицы длиннее прямой линии
EARTH_RADIUS_M = 6_371_000
MAX_WALK_DISTANCE_M = 50_000


def haversine_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def estimate_walk(origin, destination):
    distance = haversine_m(*origin, *destination) * DETOUR_FACTOR
    return {
        "distance_m": round(distance),
        "duration_s": round(distance / WALK_SPEED_MPS),
        "source": "estimate",
    }


class RoutingBusy(Exception):
    """Лимит публичного сервера исчерпан — используем оценку по прямой."""


def _take_rate_slot(attempts=4, pause=0.3):
    # Публичный OSRM FOSSGIS разрешает не больше 1 запроса в секунду. Ключ в общем
    # кэше живёт секунду: кто успел его создать, тот и отправляет запрос.
    for _ in range(attempts):
        if cache.add("walk:osrm-slot", 1, timeout=1):
            return
        time.sleep(pause)
    raise RoutingBusy()


def _osrm_get(path, base=None):
    _take_rate_slot()
    url = f"{(base or settings.OSRM_FOOT_URL).rstrip('/')}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "Ruli-carsharing/1.0"})
    with urllib.request.urlopen(request, timeout=settings.OSRM_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    if payload.get("code") != "Ok":
        raise ValueError(payload.get("message") or payload.get("code"))
    return payload


def _coords(points):
    # OSRM ожидает «долгота,широта».
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)


def _cache_key(prefix, points):
    raw = "|".join(f"{lat:.4f},{lon:.4f}" for lat, lon in points)
    return f"walk:{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"


def walking_matrix(origin, destinations):
    """Время и расстояние пешком от origin до каждой точки destinations."""
    if not destinations:
        return []

    key = _cache_key("table", [origin, *destinations])
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        payload = _osrm_get(
            f"table/v1/foot/{_coords([origin, *destinations])}"
            "?sources=0&annotations=duration,distance"
        )
        durations = payload["durations"][0][1:]
        distances = payload["distances"][0][1:]
        result = [
            {"distance_m": round(dist), "duration_s": round(dur), "source": "osrm"}
            if dur is not None and dist is not None
            else estimate_walk(origin, point)
            for dur, dist, point in zip(durations, distances, destinations)
        ]
        cache.set(key, result, settings.WALK_CACHE_SECONDS)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, RoutingBusy):
        # Без кэширования: как только сервис вернётся, получим точные данные.
        result = [estimate_walk(origin, point) for point in destinations]
    return result


def walking_route(origin, destination):
    """Маршрут пешком: геометрия линии (список [долгота, широта]), время и расстояние."""
    key = _cache_key("route", [origin, destination])
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        payload = _osrm_get(
            f"route/v1/foot/{_coords([origin, destination])}"
            "?overview=full&geometries=geojson"
        )
        route = payload["routes"][0]
        # OSRM «прилипает» к ближайшей дорожке — достраиваем линию до реальных точек.
        geometry = [
            [origin[1], origin[0]],
            *route["geometry"]["coordinates"],
            [destination[1], destination[0]],
        ]
        result = {
            "distance_m": round(route["distance"]),
            "duration_s": round(route["duration"]),
            "geometry": geometry,
            "source": "osrm",
        }
        cache.set(key, result, settings.WALK_CACHE_SECONDS * 10)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, RoutingBusy):
        result = {
            **estimate_walk(origin, destination),
            "geometry": [[origin[1], origin[0]], [destination[1], destination[0]]],
        }
    return result


def parse_point(lat, lng):
    """Координаты клиента из query-параметров; None, если их нет или они некорректны."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    # ~11 м точности достаточно для пешего маршрута, а внешний сервер не получает точный адрес.
    return round(lat, 4), round(lng, 4)

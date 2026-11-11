"""Время в пути на машине: OSRM с автомобильным профилем, при недоступности — оценка по прямой."""

import urllib.error

from django.conf import settings
from django.core.cache import cache

from .walking import RoutingBusy, _cache_key, _coords, _osrm_get, haversine_m

CITY_SPEED_MPS = 8.3  # ~30 км/ч в среднем по Минску со светофорами
DRIVE_DETOUR = 1.35
ROUTING_ERRORS = (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, RoutingBusy)


def estimate_drive(origin, destination):
    distance = haversine_m(*origin, *destination) * DRIVE_DETOUR
    return {"distance_m": round(distance), "duration_s": round(distance / CITY_SPEED_MPS), "source": "estimate"}


def driving_table(sources, destination):
    """Время и расстояние на машине от каждой точки sources до destination — одним запросом."""
    if not sources:
        return []
    key = _cache_key("drive-table", [*sources, destination])
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        last = len(sources)
        payload = _osrm_get(
            f"table/v1/driving/{_coords([*sources, destination])}"
            f"?sources={';'.join(map(str, range(last)))}&destinations={last}&annotations=duration,distance",
            base=settings.OSRM_CAR_URL,
        )
        result = [
            {"distance_m": round(dist[0]), "duration_s": round(dur[0]), "source": "osrm"}
            if dur[0] is not None and dist[0] is not None
            else estimate_drive(point, destination)
            for dur, dist, point in zip(payload["durations"], payload["distances"], sources)
        ]
        cache.set(key, result, settings.WALK_CACHE_SECONDS * 5)
    except ROUTING_ERRORS:
        result = [estimate_drive(point, destination) for point in sources]
    return result


def driving_route(origin, destination):
    """Линия маршрута на машине для карты (список [долгота, широта])."""
    key = _cache_key("drive-route", [origin, destination])
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        payload = _osrm_get(
            f"route/v1/driving/{_coords([origin, destination])}?overview=full&geometries=geojson",
            base=settings.OSRM_CAR_URL,
        )
        route = payload["routes"][0]
        result = {
            "distance_m": round(route["distance"]),
            "duration_s": round(route["duration"]),
            "geometry": route["geometry"]["coordinates"],
            "source": "osrm",
        }
        cache.set(key, result, settings.WALK_CACHE_SECONDS * 10)
    except ROUTING_ERRORS:
        result = {
            **estimate_drive(origin, destination),
            "geometry": [[origin[1], origin[0]], [destination[1], destination[0]]],
        }
    return result

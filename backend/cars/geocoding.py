"""Поиск адреса для «Куда едем?» — Nominatim (OpenStreetMap) через бэкенд.

Запросы идут с сервера: так соблюдаются правила Nominatim (свой User-Agent,
не чаще раза в секунду, кэш), а браузер клиента не передаёт адрес третьей стороне.
"""

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

# Минск с окрестностями: поиск не уводит в одноимённые улицы других городов.
MINSK_VIEWBOX = "27.30,54.05,27.85,53.78"
ERRORS = (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError)


class GeocoderBusy(Exception):
    pass


def _slot():
    for _ in range(5):
        if cache.add("geo:slot", 1, timeout=1):
            return
        time.sleep(0.25)
    raise GeocoderBusy()


def _get(path, params):
    _slot()
    url = f"{settings.GEOCODER_URL.rstrip('/')}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "Ruli-carsharing/1.0 (coursework)"})
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.load(response)


def _label(item):
    address = item.get("address") or {}
    street = address.get("road") or address.get("pedestrian") or address.get("square")
    house = address.get("house_number")
    name = item.get("name")
    parts = []
    if name and name != street:
        parts.append(name)
    if street:
        parts.append(f"{street}, {house}" if house else street)
    if not parts:
        parts.append(item.get("display_name", "").split(",")[0])
    district = address.get("suburb") or address.get("city_district") or address.get("city")
    return " · ".join(parts), district or ""


def search(query):
    query = " ".join(query.split())[:120]
    if len(query) < 3:
        return []
    key = "geo:q:" + hashlib.md5(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        items = _get(
            "search",
            {
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "accept-language": "ru",
                "countrycodes": "by",
                "viewbox": MINSK_VIEWBOX,
                "bounded": 1,
                "limit": 6,
            },
        )
    except (*ERRORS, GeocoderBusy):
        return []
    result = []
    for item in items:
        title, subtitle = _label(item)
        result.append({"title": title, "subtitle": subtitle, "lat": float(item["lat"]), "lng": float(item["lon"])})
    cache.set(key, result, 24 * 3600)
    return result


def reverse(lat, lng):
    key = f"geo:r:{lat:.4f},{lng:.4f}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    fallback = {"title": "Точка на карте", "subtitle": f"{lat:.4f}, {lng:.4f}", "lat": lat, "lng": lng}
    try:
        item = _get(
            "reverse",
            {"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1, "accept-language": "ru", "zoom": 18},
        )
    except (*ERRORS, GeocoderBusy):
        return fallback
    if "error" in item:
        return fallback
    title, subtitle = _label(item)
    result = {"title": title or fallback["title"], "subtitle": subtitle, "lat": lat, "lng": lng}
    cache.set(key, result, 24 * 3600)
    return result

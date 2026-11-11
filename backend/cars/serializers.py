from rest_framework import serializers

from .models import Car, Tariff


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = (
            "id",
            "name",
            "price_per_minute",
            "waiting_price_per_minute",
            "price_per_hour",
            "price_per_day",
        )


class CarSerializer(serializers.ModelSerializer):
    tariff = TariffSerializer(read_only=True)
    title = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    features = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    car_class_display = serializers.CharField(source="get_car_class_display", read_only=True)
    transmission_display = serializers.CharField(
        source="get_transmission_display", read_only=True
    )
    fuel_type_display = serializers.CharField(source="get_fuel_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    walk = serializers.SerializerMethodField()
    free_booking_minutes = serializers.SerializerMethodField()
    eligibility = serializers.SerializerMethodField()
    livery_display = serializers.CharField(source="get_livery_display", read_only=True)
    is_signature = serializers.BooleanField(read_only=True)

    class Meta:
        model = Car
        fields = (
            "id",
            "brand",
            "model",
            "title",
            "year",
            "license_plate",
            "car_class",
            "car_class_display",
            "transmission",
            "transmission_display",
            "fuel_type",
            "fuel_type_display",
            "engine_volume",
            "horsepower",
            "color",
            "livery",
            "livery_display",
            "is_signature",
            "seats",
            "features",
            "tariff",
            "status",
            "status_display",
            "latitude",
            "longitude",
            "address",
            "image",
            "odometer_km",
            "fuel_level_percent",
            "walk",
            "free_booking_minutes",
            "eligibility",
        )

    def get_image(self, obj):
        if obj.photo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return obj.photo_url or None

    def get_walk(self, obj):
        # Заполняется во ViewSet, только если клиент передал свои координаты.
        return getattr(obj, "walk", None)

    def _policy(self):
        return self.context.get("access_policy")

    def get_free_booking_minutes(self, obj):
        """Сколько бесплатных минут даст бронь, если клиент сейчас там, откуда смотрит."""
        walk = getattr(obj, "walk", None)
        if not walk:
            return None
        from rentals.services import free_waiting_minutes_for, origin_is_plausible

        # То же правило, что при брони: издалека обещаем только стандартное окно.
        plausible = origin_is_plausible(self.context.get("origin"), obj)
        policy = self._policy()
        return free_waiting_minutes_for(
            walk["duration_s"] if plausible else None, policy["level"] if policy else 0
        )

    def get_eligibility(self, obj):
        policy = self._policy()
        if policy is None:
            return {"allowed": False, "code": "login_required", "hint": "Войдите, чтобы бронировать.", "unlock_on": None}
        entry = policy["classes"].get(obj.car_class)
        if entry is None:
            return {"allowed": True, "code": None, "hint": "", "unlock_on": None}
        code = None
        if not entry["allowed"]:
            reasons = entry["reasons"]
            code = "verification" if "verification" in reasons else ("phone" if "phone" in reasons else "class_locked")
        return {
            "allowed": entry["allowed"],
            "code": code,
            "hint": entry["hint"],
            "unlock_on": entry["unlock_on"],
        }

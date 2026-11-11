from django.core.cache import cache
from rest_framework import serializers

from .chain import integrity_cache_key, verify_chain
from .models import Damage, Inspection
from .services import cleanliness_score


class DamageSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    first_seen_at = serializers.DateTimeField(source="first_seen.created_at", read_only=True)
    seal_short = serializers.CharField(source="first_seen.seal_short", read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Damage
        fields = (
            "id",
            "x",
            "y",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "first_seen_at",
            "seal_short",
            "photo_url",
        )

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        url = obj.photo.image.url
        return request.build_absolute_uri(url) if request else url


class InspectionBriefSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    seal_short = serializers.CharField(read_only=True)

    class Meta:
        model = Inspection
        fields = ("id", "kind", "kind_display", "seal_short", "seal_hash", "created_at", "cleanliness")


def cached_integrity(car):
    key = integrity_cache_key(car.pk)
    result = cache.get(key)
    if result is None:
        result = verify_chain(car)
        cache.set(key, result, 60)
    return result


def passport_payload(car, request=None, fresh=False):
    damages = car.damages.exclude(status=Damage.Status.REPAIRED).select_related("first_seen", "photo")
    inspections = car.inspections.all()
    last = inspections.order_by("-created_at").first()
    return {
        "car": car.pk,
        "is_signature": car.is_signature,
        "livery": car.livery,
        "damages": DamageSerializer(damages, many=True, context={"request": request}).data,
        "chain_length": inspections.count(),
        "last_inspection_at": last.created_at if last else None,
        "last_seal": last.seal_short if last else None,
        "cleanliness_score": cleanliness_score(car),
        "last_cleaned_at": car.last_cleaned_at,
        "needs_cleaning": car.needs_cleaning,
        "integrity": verify_chain(car) if fresh else cached_integrity(car),
    }

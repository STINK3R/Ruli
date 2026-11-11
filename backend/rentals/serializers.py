from django.conf import settings
from rest_framework import serializers

from cars.serializers import CarSerializer

from .models import Rental


class RentalSerializer(serializers.ModelSerializer):
    car = CarSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    trip_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    free_waiting_until = serializers.DateTimeField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    cancel_reason_display = serializers.CharField(source="get_cancel_reason_display", read_only=True)
    inspections = serializers.SerializerMethodField()
    signature_guarantee = serializers.SerializerMethodField()
    face_check = serializers.SerializerMethodField()
    rewards = serializers.SerializerMethodField()

    class Meta:
        model = Rental
        fields = (
            "id",
            "user",
            "user_username",
            "car",
            "status",
            "status_display",
            "reserved_at",
            "free_waiting_until",
            "started_at",
            "finished_at",
            "price_per_minute_at_booking",
            "waiting_price_per_minute_at_booking",
            "price_per_hour_at_booking",
            "price_per_day_at_booking",
            "duration_minutes",
            "free_waiting_minutes",
            "walk_duration_s",
            "walk_distance_m",
            "cancel_reason",
            "cancel_reason_display",
            "compensation_minutes",
            "signature_guarantee",
            "face_check",
            "points_spent",
            "points_discount",
            "rewards",
            "inspections",
            "waiting_cost",
            "trip_cost",
            "total_cost",
            "start_latitude",
            "start_longitude",
            "end_latitude",
            "end_longitude",
        )
        read_only_fields = fields

    def get_inspections(self, obj):
        from inspections.serializers import InspectionBriefSerializer

        return InspectionBriefSerializer(obj.inspections.all(), many=True).data

    def get_rewards(self, obj):
        """Что принесла эта поездка в «Движе»: баллы, достижения, задания."""
        if obj.status != obj.Status.COMPLETED:
            return []
        return [
            {"title": entry.title, "amount": entry.amount, "kind": entry.kind}
            for entry in obj.points_entries.filter(amount__gt=0, user_id=obj.user_id)
        ]

    def get_face_check(self, obj):
        check = obj.driver_check
        passed = bool(check and check.status == "passed" and check.created_at >= obj.reserved_at)
        return {"required": settings.TRIP_FACE_CHECK_REQUIRED, "passed": passed, "demo": settings.KYC_DEMO_MODE}

    def get_signature_guarantee(self, obj):
        """Обещание до осмотра: грязная машина в оклейке — первые минуты бесплатно."""
        from inspections.services import signature_guarantee_available

        available = obj.car.is_signature and signature_guarantee_available(
            obj.user_id, exclude_rental_id=obj.pk
        )
        return {"available": available, "minutes": settings.SIGNATURE_COMPENSATION_MINUTES}


class RentalCreateSerializer(serializers.Serializer):
    car = serializers.IntegerField()
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, min_value=-180, max_value=180)


class CarMissingSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)

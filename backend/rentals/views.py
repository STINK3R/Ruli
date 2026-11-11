import json
import math

from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts import kyc
from accounts.models import LivenessCheck
from accounts.verification import access_policy
from accounts.verification_views import is_demo_request, liveness_payload
from cars.serializers import CarSerializer

from .models import Rental
from .permissions import IsOwnerOrAdmin
from .serializers import CarMissingSerializer, RentalCreateSerializer, RentalSerializer
from .services import (
    cancel_rental,
    finish_rental,
    report_car_missing,
    reserve_car,
    start_rental,
)


def _optional_point(lat, lng):
    """Координаты акта осмотра: только конечные числа в пределах Земли, иначе акт без координат."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None
    if not (math.isfinite(lat) and math.isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180):
        return None, None
    return lat, lng


class RentalViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RentalSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrAdmin)
    filterset_fields = ("status",)
    ordering_fields = ("reserved_at", "total_cost")
    throttle_scope = None  # лимит включается только у «Машины нет на месте»

    def get_queryset(self):
        queryset = Rental.objects.select_related("car__tariff", "user", "driver_check").prefetch_related(
            "car__features", "inspections"
        )
        # «Мои поездки» — только свои даже у сотрудника; все аренды — в админке.
        if self.action == "list" or not self.request.user.is_staff:
            return queryset.filter(user=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = RentalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # ~11 м точности: для расчёта пути хватает, а точный адрес клиента не уходит наружу.
        origin = (round(data["lat"], 4), round(data["lng"], 4)) if "lat" in data and "lng" in data else None
        rental = reserve_car(request.user, data["car"], origin=origin)
        return Response(
            RentalSerializer(rental, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Текущая бронь или поездка пользователя (для виджета на фронтенде)."""
        rental = (
            self.get_queryset()
            .filter(user=request.user, status__in=Rental.ACTIVE_STATUSES)
            .first()
        )
        return Response(self.get_serializer(rental).data if rental else None)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        rental = start_rental(self.get_object())
        return Response(self.get_serializer(rental).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        use_points = str(request.data.get("use_points", "")).lower() in ("1", "true", "yes")
        rental = finish_rental(self.get_object(), use_points=use_points)
        return Response(self.get_serializer(rental).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        rental = cancel_rental(self.get_object())
        return Response(self.get_serializer(rental).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="car-missing",
        throttle_classes=(ScopedRateThrottle,),
        throttle_scope="car_missing",
    )
    def car_missing(self, request, pk=None):
        """Клиент дошёл, а машины нет: бронь без оплаты и ближайшая замена."""
        serializer = CarMissingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        origin = (round(serializer.validated_data["lat"], 4), round(serializer.validated_data["lng"], 4))
        rental = self.get_object()
        policy = access_policy(rental.user)
        rental, alternative = report_car_missing(rental, origin, policy=policy)
        payload = {"rental": self.get_serializer(rental).data, "alternative": None}
        if alternative:
            # Тот же контекст, что в каталоге: допуск и точка клиента — бесплатные минуты
            # и доступность замены считаются по правилам брони.
            context = {**self.get_serializer_context(), "access_policy": policy, "origin": origin}
            payload["alternative"] = CarSerializer(alternative, context=context).data
        return Response(payload)

    def _own_reserved(self):
        rental = self.get_object()
        if rental.user_id != self.request.user.id:
            raise ValidationError("Проверку лица проходит только водитель этой брони.")
        if rental.status != Rental.Status.RESERVED:
            raise ValidationError("Проверка лица нужна только перед стартом поездки.")
        return rental

    @action(
        detail=True,
        methods=["post"],
        url_path="face-check/start",
        throttle_classes=(ScopedRateThrottle,),
        throttle_scope="liveness",
    )
    def face_check_start(self, request, pk=None):
        """Начать проверку «за рулём владелец»: одно случайное движение, две минуты."""
        self._own_reserved()
        check = kyc.start_liveness(request.user, LivenessCheck.Purpose.TRIP)
        return Response(liveness_payload(check), status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="face-check",
        parser_classes=(MultiPartParser, FormParser),
    )
    def face_check(self, request, pk=None):
        rental = self._own_reserved()
        check = get_object_or_404(
            LivenessCheck, pk=request.data.get("check"), user=request.user, purpose=LivenessCheck.Purpose.TRIP
        )
        kyc.complete_liveness(check, request.FILES, demo=is_demo_request(request))
        rental.driver_check = check
        rental.save(update_fields=["driver_check"])
        return Response(self.get_serializer(rental).data)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=(MultiPartParser, FormParser, JSONParser),
    )
    def inspections(self, request, pk=None):
        """Акт осмотра: 4 ракурса (+ салон, если грязно), отметки повреждений и чистота."""
        from inspections.serializers import DamageSerializer, InspectionBriefSerializer
        from inspections.services import create_inspection

        rental = self.get_object()
        if rental.user_id != request.user.id:
            raise ValidationError("Осмотр делает только водитель этой аренды.")

        photos = {
            angle: request.FILES[angle]
            for angle in ("front", "rear", "left", "right", "interior")
            if angle in request.FILES
        }
        try:
            marks = json.loads(request.data.get("damages") or "[]")
        except (TypeError, ValueError):
            raise ValidationError({"damages": "Отметки должны быть JSON-списком."})
        cleanliness = request.data.get("cleanliness")
        lat, lng = _optional_point(request.data.get("lat"), request.data.get("lng"))
        inspection, new_damages = create_inspection(
            rental,
            request.user,
            kind=request.data.get("kind"),
            photos=photos,
            marks=marks if isinstance(marks, list) else [],
            cleanliness=int(cleanliness) if cleanliness not in (None, "") else None,
            confirmed=str(request.data.get("confirmed", "")).lower() in ("1", "true", "yes"),
            lat=lat,
            lng=lng,
        )
        rental.refresh_from_db()
        return Response(
            {
                "inspection": InspectionBriefSerializer(inspection).data,
                "new_damages": DamageSerializer(new_damages, many=True, context={"request": request}).data,
                "rental": self.get_serializer(rental).data,
            },
            status=status.HTTP_201_CREATED,
        )

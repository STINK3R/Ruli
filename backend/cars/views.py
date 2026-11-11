from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.verification import access_policy

from .filters import CarFilter
from .models import Car, Tariff
from .serializers import CarSerializer, TariffSerializer
from . import geocoding
from .planner import plan_trip
from .walking import MAX_WALK_DISTANCE_M, haversine_m, parse_point, walking_matrix, walking_route


class CarViewSet(viewsets.ReadOnlyModelViewSet):
    """Каталог автомобилей. Изменение автопарка — через админ-панель Django.

    Если переданы координаты клиента (?lat=&lng=), у каждой машины появляется
    поле walk с временем и расстоянием пешком, а список сортируется от ближайшей.
    """

    queryset = Car.objects.select_related("tariff").prefetch_related("features")
    serializer_class = CarSerializer
    permission_classes = (permissions.AllowAny,)
    filterset_class = CarFilter
    search_fields = ("brand", "model", "license_plate")
    ordering_fields = ("tariff__price_per_minute", "year", "brand")
    throttle_scope = None  # лимит только у планировщика: он ходит во внешний сервис маршрутов

    def _origin(self):
        params = self.request.query_params
        return parse_point(params.get("lat"), params.get("lng"))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Откуда смотрит клиент: по этому же правилу считается окно при брони.
        context["origin"] = self._origin()
        user = self.request.user
        if user.is_authenticated:
            # Допуск считается один раз на запрос, а не для каждой машины.
            context["access_policy"] = access_policy(user)
        return context

    def list(self, request, *args, **kwargs):
        origin = self._origin()
        if origin is None:
            return super().list(request, *args, **kwargs)

        cars = list(self.filter_queryset(self.get_queryset()))
        walks = walking_matrix(origin, [(car.latitude, car.longitude) for car in cars])
        for car, walk in zip(cars, walks):
            car.walk = walk

        # Явная сортировка по цене/году важнее, по умолчанию — ближайшие сверху.
        if not request.query_params.get("ordering"):
            cars.sort(key=lambda car: car.walk["duration_s"])

        page = self.paginate_queryset(cars)
        serializer = self.get_serializer(page if page is not None else cars, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        throttle_classes=(ScopedRateThrottle,),
        throttle_scope="planner",
    )
    def plan(self, request):
        """«Куда едем?»: полная цена и время поездки до точки для ближайших машин."""
        params = request.query_params
        origin = self._origin()
        destination = parse_point(params.get("to_lat"), params.get("to_lng"))
        if origin is None or destination is None:
            raise ValidationError("Нужны обе точки: ?lat=&lng= (откуда) и ?to_lat=&to_lng= (куда).")
        policy = access_policy(request.user) if request.user.is_authenticated else None
        plan = plan_trip(origin, destination, policy)
        context = {**self.get_serializer_context(), "origin": origin}
        options = [
            {
                **{key: value for key, value in option.items() if key != "car"},
                "car": CarSerializer(option["car"], context=context).data,
            }
            for option in plan["options"]
        ]
        return Response({**plan, "options": options})

    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """Пешеходный маршрут от клиента до машины: линия, время и расстояние."""
        origin = self._origin()
        if origin is None:
            raise ValidationError("Передайте координаты клиента: ?lat=…&lng=…")

        car = self.get_object()
        destination = (car.latitude, car.longitude)
        if haversine_m(*origin, *destination) > MAX_WALK_DISTANCE_M:
            raise ValidationError("Вы слишком далеко от автомобиля для пешего маршрута.")
        return Response(walking_route(origin, destination))

    @action(detail=True, methods=["get"])
    def passport(self, request, pk=None):
        """Паспорт кузова: известные повреждения, чистота и целостность цепочки актов."""
        from inspections.serializers import passport_payload

        return Response(passport_payload(self.get_object(), request))

    @action(detail=True, methods=["get"], url_path="passport/verify")
    def passport_verify(self, request, pk=None):
        """Проверка целостности цепочки актов — пересчёт всех хэшей прямо сейчас."""
        from inspections.chain import verify_chain

        return Response(verify_chain(self.get_object()))


class TariffViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tariff.objects.all()
    serializer_class = TariffSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class GeocodeView(APIView):
    """Поиск адреса по строке (?q=) или адрес точки (?lat=&lng=) — для «Куда едем?»."""

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "planner"

    def get(self, request):
        params = request.query_params
        point = parse_point(params.get("lat"), params.get("lng"))
        if point is not None:
            return Response(geocoding.reverse(*point))
        return Response(geocoding.search(params.get("q", "")))

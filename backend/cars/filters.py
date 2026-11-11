import django_filters

from .models import Car


class CarFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(
        field_name="tariff__price_per_minute", lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="tariff__price_per_minute", lookup_expr="lte"
    )

    class Meta:
        model = Car
        fields = ("car_class", "transmission", "fuel_type", "status", "seats")

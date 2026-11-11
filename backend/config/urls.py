from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cars.views import CarViewSet, GeocodeView, TariffViewSet
from rentals.views import RentalViewSet

admin.site.site_header = "Рули — панель управления"
admin.site.site_title = "Рули"
admin.site.index_title = "Автопарк, тарифы и аренды"

router = DefaultRouter()
router.register("cars", CarViewSet, basename="car")
router.register("tariffs", TariffViewSet, basename="tariff")
router.register("rentals", RentalViewSet, basename="rental")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/verification/", include("accounts.verification_urls")),
    path("api/geocode/", GeocodeView.as_view(), name="geocode"),
    path("api/rewards/", include("rewards.urls")),
    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

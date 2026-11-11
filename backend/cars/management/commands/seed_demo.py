from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.demo import ensure_demo_users
from cars.models import Car, Feature, Tariff
from inspections.demo import seed_history
from rewards.demo import seed_rewards

TARIFFS = [
    {"name": "Эконом", "price_per_minute": "0.29", "waiting_price_per_minute": "0.15",
     "price_per_hour": "12.90", "price_per_day": "69.00"},
    {"name": "Комфорт", "price_per_minute": "0.37", "waiting_price_per_minute": "0.17",
     "price_per_hour": "15.90", "price_per_day": "89.00"},
    {"name": "Бизнес", "price_per_minute": "0.55", "waiting_price_per_minute": "0.22",
     "price_per_hour": "22.90", "price_per_day": "129.00"},
    {"name": "Премиум", "price_per_minute": "0.79", "waiting_price_per_minute": "0.29",
     "price_per_hour": "32.90", "price_per_day": "189.00"},
]

CLASS_TO_TARIFF = {
    "economy": "Эконом",
    "comfort": "Комфорт",
    "business": "Бизнес",
    "premium": "Премиум",
}

BASIC = ["Кондиционер", "Bluetooth", "USB-зарядка"]
COMFORT = BASIC + ["Климат-контроль", "Подогрев сидений", "Камера заднего вида", "Мультируль"]
TOP = COMFORT + ["Сенсорное мультимедиа", "Apple CarPlay / Android Auto", "Парктроник", "Круиз-контроль"]
LUXURY = TOP + ["Кожаный салон", "Панорамная крыша", "Адаптивный круиз-контроль"]

# Фирменная оклейка «Рули Signature» — примерно у четверти парка. Ливрея подобрана
# под цвет кузова на фото: графитовая — тёмным машинам, «слоновая кость» — светлым.
# Belgee X50 без оклейки: на её фото серая машина без фирменной символики.
LIVERIES = {
    "volkswagen-polo": Car.Livery.GRAPHITE,
    "toyota-camry": Car.Livery.GRAPHITE,
    "geely-emgrand": Car.Livery.IVORY,
}

# Автопарк в Минске: реальные улицы и координаты парковок.
CARS = [
    dict(brand="Geely", model="Emgrand", year=2023, license_plate="8743 AB-7", car_class="comfort",
         transmission="automatic", fuel_type="petrol", engine_volume="1.5", horsepower=122,
         color="Белый", latitude=53.9213, longitude=27.5817, address="улица Якуба Коласа, 51",
         slug="geely-emgrand", odometer_km=42500, fuel_level_percent=62, features=TOP),
    dict(brand="Geely", model="Coolray", year=2023, license_plate="4219 CH-7", car_class="comfort",
         transmission="automatic", fuel_type="petrol", engine_volume="1.5", horsepower=147,
         color="Синий", latitude=53.9268, longitude=27.5871, address="улица Сурганова, 28",
         slug="geely-coolray", odometer_km=31800, fuel_level_percent=84, features=TOP),
    dict(brand="Belgee", model="X50", year=2024, license_plate="1056 KE-7", car_class="comfort",
         transmission="automatic", fuel_type="petrol", engine_volume="1.5", horsepower=177,
         color="Серебристый", latitude=53.9145, longitude=27.5920, address="проспект Независимости, 38",
         slug="belgee-x50", odometer_km=12400, fuel_level_percent=95, features=TOP),
    dict(brand="Renault", model="Logan", year=2021, license_plate="7382 MA-7", car_class="economy",
         transmission="manual", fuel_type="petrol", engine_volume="1.6", horsepower=102,
         color="Серебристый", latitude=53.9047, longitude=27.5510, address="улица Немига, 5",
         slug="renault-logan", odometer_km=118600, fuel_level_percent=41, features=BASIC),
    dict(brand="Kia", model="Rio", year=2020, license_plate="2914 IB-7", car_class="economy",
         transmission="automatic", fuel_type="petrol", engine_volume="1.6", horsepower=123,
         color="Красный", latitude=53.8925, longitude=27.5449, address="улица Московская, 14",
         slug="kia-rio", odometer_km=96200, fuel_level_percent=57,
         features=BASIC + ["Подогрев сидений"]),
    dict(brand="Volkswagen", model="Polo", year=2021, license_plate="6607 TA-7", car_class="economy",
         transmission="automatic", fuel_type="petrol", engine_volume="1.6", horsepower=110,
         color="Чёрный", latitude=53.9174, longitude=27.5836,
         address="площадь Якуба Коласа, 1", slug="volkswagen-polo", odometer_km=74300,
         fuel_level_percent=73, features=BASIC + ["Подогрев сидений", "Мультируль"]),
    dict(brand="Skoda", model="Rapid", year=2021, license_plate="3521 EX-7", car_class="comfort",
         transmission="automatic", fuel_type="diesel", engine_volume="1.6", horsepower=110,
         color="Красный", latitude=53.9235, longitude=27.5745, address="улица Кульман, 9",
         slug="skoda-rapid", odometer_km=88100, fuel_level_percent=19, features=COMFORT),
    dict(brand="Citroen", model="C4", year=2022, license_plate="9130 PC-7", car_class="comfort",
         transmission="automatic", fuel_type="petrol", engine_volume="1.2", horsepower=130,
         color="Серый", latitude=53.9078, longitude=27.4634, address="улица Притыцкого, 62",
         slug="citroen-c4", odometer_km=53900, fuel_level_percent=66, features=COMFORT),
    dict(brand="Lada", model="Vesta", year=2022, license_plate="5448 AM-7", car_class="economy",
         transmission="manual", fuel_type="petrol", engine_volume="1.6", horsepower=106,
         color="Серый", latitude=53.8963, longitude=27.5760, address="улица Октябрьская, 16",
         slug="lada-vesta", odometer_km=61700, fuel_level_percent=38, features=BASIC),
    dict(brand="Volkswagen", model="Tiguan", year=2023, license_plate="8802 OH-7",
         car_class="business", transmission="automatic", fuel_type="petrol",
         engine_volume="2.0", horsepower=180, color="Чёрный", latitude=53.9106, longitude=27.5449,
         address="проспект Победителей, 25", slug="volkswagen-tiguan", odometer_km=28400,
         fuel_level_percent=88, features=TOP),
    dict(brand="Toyota", model="Camry", year=2023, license_plate="7715 HB-7", car_class="business",
         transmission="automatic", fuel_type="hybrid", engine_volume="2.5", horsepower=218,
         color="Чёрный", latitude=53.9128, longitude=27.5560, address="проспект Машерова, 17",
         slug="toyota-camry", odometer_km=35600, fuel_level_percent=79, features=TOP),
    dict(brand="BMW", model="3 series", year=2023, license_plate="1188 KA-7", car_class="premium",
         transmission="automatic", fuel_type="petrol", engine_volume="2.0", horsepower=245,
         color="Серый", latitude=53.8615, longitude=27.4860,
         address="проспект Дзержинского, 104", slug="bmw-3-series", odometer_km=19800,
         fuel_level_percent=91, features=LUXURY),
]


class Command(BaseCommand):
    help = "Заполняет пустую базу автопарком Минска, тарифами в BYN и тестовыми пользователями."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписать автомобили и тарифы, даже если база уже заполнена",
        )

    def handle(self, *args, force=False, **options):
        users = ensure_demo_users(self.stdout)

        if Car.objects.exists() and not force:
            self.stdout.write("Автопарк уже заполнен — пропускаю (используйте --force).")
            seed_history(users["demo"], self.stdout)
            seed_rewards(self.stdout)
            return

        tariffs = {}
        for data in TARIFFS:
            values = {key: Decimal(value) for key, value in data.items() if key != "name"}
            tariff, _ = Tariff.objects.update_or_create(name=data["name"], defaults=values)
            tariffs[tariff.name] = tariff

        features = {
            name: Feature.objects.get_or_create(name=name)[0]
            for name in {feature for item in CARS for feature in item["features"]}
        }

        for item in CARS:
            data = dict(item)
            slug = data.pop("slug")
            plate = data.pop("license_plate")
            car_features = data.pop("features")
            data["engine_volume"] = Decimal(data["engine_volume"])
            data["tariff"] = tariffs[CLASS_TO_TARIFF[data["car_class"]]]
            data["photo_url"] = f"/cars/{slug}.webp"
            data["livery"] = LIVERIES.get(slug, Car.Livery.NONE)
            data["status"] = Car.Status.AVAILABLE
            car, _ = Car.objects.update_or_create(license_plate=plate, defaults=data)
            car.features.set(features[name] for name in car_features)

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: {Tariff.objects.count()} тарифа, {Car.objects.count()} автомобилей, "
                f"{Feature.objects.count()} опций."
            )
        )
        seed_history(users["demo"], self.stdout)
        seed_rewards(self.stdout)

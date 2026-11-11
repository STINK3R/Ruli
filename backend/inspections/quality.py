import hashlib
from io import BytesIO

from django.conf import settings
from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

# Защита от «декомпрессионных бомб»: крошечный файл с огромными размерами.
MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
TOO_MANY_PIXELS = "Фото больше 25 мегапикселей."
OPEN_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_SIDE_PX = 1600
# Лапласиан: на резком фото много перепадов яркости — велико стандартное отклонение.
LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)

HINTS = {
    "too_dark": "Слишком темно — включите вспышку или подойдите к фонарю.",
    "too_blurry": "Фото смазано — держите телефон неподвижно.",
}


class PhotoQualityError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "photo_quality"


def measure(image):
    """Яркость (0–255) и резкость фото на уменьшенной копии в оттенках серого."""
    probe = image.convert("L")
    probe.thumbnail((512, 512))
    brightness = ImageStat.Stat(probe).mean[0]
    sharpness = ImageStat.Stat(probe.filter(LAPLACIAN)).stddev[0]
    return brightness, sharpness


def process_inspection_photo(uploaded, angle):
    """Проверяет фото осмотра и пересохраняет его в WebP без EXIF.

    SHA-256 считается по сохранённым байтам — именно их потом пересчитывает
    проверка целостности цепочки.
    """
    if uploaded.size > MAX_UPLOAD_BYTES:
        raise ValidationError({angle: "Файл больше 8 МБ."})
    try:
        image = Image.open(uploaded, formats=OPEN_FORMATS)
    except Image.DecompressionBombError:
        # Больше 2 × MAX_IMAGE_PIXELS Pillow отвергает сам — это та же «слишком большая» фотография.
        raise ValidationError({angle: TOO_MANY_PIXELS})
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError({angle: "Это не похоже на фотографию."})
    # Размеры известны из заголовка — проверяем до распаковки пикселей.
    if image.width * image.height > MAX_PIXELS:
        raise ValidationError({angle: TOO_MANY_PIXELS})
    try:
        if image.format in ("JPEG", "MPO"):
            # JPEG сразу декодируется в уменьшенном масштабе — без полноразмерной копии.
            image.draft("RGB", (MAX_SIDE_PX, MAX_SIDE_PX))
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError({angle: "Это не похоже на фотографию."})

    ImageOps.exif_transpose(image, in_place=True)
    if image.mode != "RGB":
        image = image.convert("RGB")
    brightness, sharpness = measure(image)
    if brightness < settings.INSPECTION_MIN_BRIGHTNESS:
        raise PhotoQualityError({"angle": angle, "code": "too_dark", "detail": HINTS["too_dark"]})
    if sharpness < settings.INSPECTION_MIN_SHARPNESS:
        raise PhotoQualityError({"angle": angle, "code": "too_blurry", "detail": HINTS["too_blurry"]})

    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=82, method=4)
    content = buffer.getvalue()
    return content, {
        "sha256": hashlib.sha256(content).hexdigest(),
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 2),
    }

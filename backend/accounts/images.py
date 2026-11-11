import hashlib
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

# Защита от «декомпрессионных бомб»: крошечный файл с огромными размерами.
MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
TOO_MANY_PIXELS = "Фото больше 25 мегапикселей — уменьшите его и загрузите снова."

# Другие декодеры Pillow даже не пробуются. MPO (JPEG с телефонов) открывает плагин JPEG.
OPEN_FORMATS = ("JPEG", "PNG", "WEBP")
MIN_SIDE_PX = 300
MAX_SIDE_PX = 2000
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 36867


def _captured_at(image):
    try:
        raw = image.getexif().get_ifd(EXIF_IFD).get(DATETIME_ORIGINAL)
        if raw:
            return timezone.make_aware(datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S"))
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def process_document_image(uploaded):
    """Проверяет загруженный документ и пересохраняет его без EXIF.

    Формат определяется по содержимому, а не по имени файла. EXIF удаляется
    целиком: в нём бывают GPS-координаты и модель телефона. Дата съёмки
    считывается до удаления — по ней проверяется свежесть селфи.
    """
    max_bytes = settings.VERIFICATION_MAX_UPLOAD_MB * 1024 * 1024
    if uploaded.size > max_bytes:
        raise ValidationError(f"Файл больше {settings.VERIFICATION_MAX_UPLOAD_MB} МБ.")

    raw = uploaded.read()
    try:
        probe = Image.open(BytesIO(raw), formats=OPEN_FORMATS)
        probe.verify()
        image = Image.open(BytesIO(raw), formats=OPEN_FORMATS)
    except Image.DecompressionBombError:
        # Больше 2 × MAX_IMAGE_PIXELS Pillow отвергает сам — это та же «слишком большая» фотография.
        raise ValidationError(TOO_MANY_PIXELS)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Это не похоже на фотографию. Загрузите JPEG, PNG или WebP.")

    # Размеры известны из заголовка — проверяем до распаковки пикселей.
    if image.width * image.height > MAX_PIXELS:
        raise ValidationError(TOO_MANY_PIXELS)
    if min(image.size) < MIN_SIDE_PX:
        raise ValidationError("Фото слишком маленькое — документ не разобрать.")

    captured_at = _captured_at(image)
    try:
        if image.format in ("JPEG", "MPO"):
            # JPEG сразу декодируется в уменьшенном масштабе — без полноразмерной копии.
            image.draft("RGB", (MAX_SIDE_PX, MAX_SIDE_PX))
        image.load()
        ImageOps.exif_transpose(image, in_place=True)
        if image.mode != "RGB":
            image = image.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError("Фото повреждено — загрузите другое.")
    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=85, optimize=True)
    content = buffer.getvalue()
    return ContentFile(content), {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": image.width,
        "height": image.height,
        "size_bytes": len(content),
        "captured_at": captured_at,
    }

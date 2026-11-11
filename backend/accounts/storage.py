import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDocumentStorage(FileSystemStorage):
    """Хранилище сканов документов вне MEDIA_ROOT.

    MEDIA_ROOT раздаёт nginx всем подряд, а фото прав и селфи — персональные
    (селфи — биометрические) данные. Эти файлы лежат в отдельном томе, к которому
    есть доступ только у бэкенда, и отдаются лишь через проверяющие права view.
    """

    def __init__(self, **kwargs):
        kwargs["base_url"] = None
        super().__init__(**kwargs)

    # Путь читается из настроек при каждом обращении — работает override_settings в тестах.
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise NotImplementedError("Документы не раздаются по прямой ссылке.")


private_document_storage = PrivateDocumentStorage()


def document_upload_path(instance, filename):
    # Имя без ФИО, id и номера прав — по пути к файлу владельца не вычислить.
    return f"verification/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"

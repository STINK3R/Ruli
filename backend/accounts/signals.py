from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import LivenessFrame, VerificationDocument


@receiver(post_delete, sender=VerificationDocument)
@receiver(post_delete, sender=LivenessFrame)
def delete_document_file(sender, instance, **kwargs):
    """Единственное место, где удаляются файлы документов и кадров «живости»: и при явном
    удалении, и при каскаде (заявка или пользователь в админке).

    Удаляем после коммита: при откате транзакции строка вернётся, и файл ей ещё нужен.
    """
    name = instance.file.name
    if not name:
        return
    storage = instance.file.storage
    transaction.on_commit(lambda: storage.delete(name))

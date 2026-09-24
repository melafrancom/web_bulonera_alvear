"""
Señales de ciclo de vida para el modelo ImageAsset.

Orquesta el desencadenamiento asíncrono de tareas Celery tras la persistencia
confirmada de imágenes en base de datos.
"""
import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ImageAsset, ImageType

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ImageAsset)
def process_image_asset(sender, instance, created, **kwargs):
    """
    Encola el procesamiento WebP en Celery tras confirmar la transacción en base de datos.

    QUÉ:
        Captura el evento post_save de ImageAsset y programa la tarea de optimización
        y generación de variantes WebP para tipos procesables.

    POR QUÉ:
        Resuelve la condición de carrera (AUD-MB-003) donde un worker de Celery intentaba
        leer la instancia antes de que el commit de base de datos finalizara, provocando
        ImageAsset.DoesNotExist o procesando datos obsoletos.

    CÓMO:
        1. Valida que el asset tenga un archivo físico asociado.
        2. Filtra por tipos que admiten generación automática de WebP.
        3. Registra el callback con transaction.on_commit() para garantizar que la tarea
           sólo se encole si la transacción actual hace commit exitoso en la BD.
    """
    # 1. Validación de existencia de archivo
    if not instance.file or not instance.file.name:
        return

    # REGLA: Tipos que admiten y requieren variantes WebP pre-generadas
    PROCESSABLE_TYPES = (
        ImageType.PRODUCT,
        ImageType.CAROUSEL,
        ImageType.BANNER,
        ImageType.CATEGORY,
        ImageType.SUBCATEGORY,
    )

    if instance.image_type in PROCESSABLE_TYPES:
        try:
            from store.tasks import process_image_asset_task
            # POR QUÉ: transaction.on_commit evita que Celery lea antes del commit
            asset_id = instance.id
            transaction.on_commit(lambda: process_image_asset_task.delay(asset_id))
        except Exception as e:
            logger.error(
                f"Error al encolar procesamiento de ImageAsset {instance.id}: {e}",
                exc_info=True
            )

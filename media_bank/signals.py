from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ImageAsset, ImageType

@receiver(post_save, sender=ImageAsset)
def process_image_asset(sender, instance, created, **kwargs):
    """Dispara procesamiento WebP al crear/actualizar un ImageAsset."""
    if not instance.file or not instance.file.name:
        return
    
    # Tipos que generan WebP automáticamente
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
            process_image_asset_task.delay(instance.id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to queue processing for ImageAsset {instance.id}: {e}")


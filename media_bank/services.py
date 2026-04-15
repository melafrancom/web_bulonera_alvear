"""Media Bank Services"""
from typing import Optional, List
from django.core.files.base import File
from .models import ImageAsset, ImageType


class MediaBankService:
    """Servicio de banco de imágenes centralizado."""

    @staticmethod
    def create_image(
        file: File,
        image_type: str = ImageType.PRODUCT,
        name: Optional[str] = None,
        alt_text: Optional[str] = None
    ) -> ImageAsset:
        """
        Crea un nuevo asset de imagen en el banco.
        
        Args:
            file: Archivo de imagen (InMemoryUploadedFile o similar)
            image_type: Tipo de imagen (product, category, subcategory, carousel)
            name: Nombre descriptivo (opcional, se auto-genera si vacío)
            alt_text: Texto alternativo para SEO
            
        Returns:
            ImageAsset creado
        """
        image_asset = ImageAsset(
            file=file,
            image_type=image_type,
            name=name or '',
            alt_text=alt_text or ''
        )
        image_asset.save()
        # Aquí se dispararía process_product_image o process_carousel_image via Celery
        # if image_type in [ImageType.PRODUCT, ImageType.CAROUSEL]:
        #     from store.tasks import process_product_image, process_carousel_image
        #     if image_type == ImageType.PRODUCT:
        #         process_product_image.delay(image_asset.id)
        #     elif image_type == ImageType.CAROUSEL:
        #         process_carousel_image.delay(image_asset.id)
        return image_asset

    @staticmethod
    def get_images_by_type(image_type: str) -> List[ImageAsset]:
        """
        Obtiene todas las imágenes de un tipo específico.
        
        Args:
            image_type: Tipo de imagen a filtrar
            
        Returns:
            QuerySet de ImageAsset
        """
        return ImageAsset.objects.filter(image_type=image_type).order_by('-uploaded_at')

    @staticmethod
    def get_all_images() -> List[ImageAsset]:
        """Obtiene todas las imágenes del banco."""
        return ImageAsset.objects.all().order_by('-uploaded_at')

"""
Capa de Servicios para media_bank.

Centraliza la lógica de negocio, validaciones de dominio, transaccionalidad
y operaciones de persistencia sobre el catálogo de ImageAsset.
"""
from typing import Optional, Sequence
from django.core.files.base import File
from django.db import transaction
from django.db.models import QuerySet
from .models import ImageAsset, ImageType


class MediaBankService:
    """
    Servicio de orquestación y gestión del banco de imágenes centralizado.

    Aplica el estándar canónico de 4 capas asegurando que toda mutación
    pase por validaciones de dominio (full_clean) y transacciones atómicas.
    """

    @staticmethod
    def create_image(
        file: File,
        image_type: str = ImageType.PRODUCT,
        name: Optional[str] = None,
        alt_text: Optional[str] = None
    ) -> ImageAsset:
        """
        Crea, valida y persiste un nuevo ImageAsset en el banco multimedia.

        QUÉ:
            Instancia un ImageAsset, ejecuta validación de modelo e integridad de archivo
            (full_clean) y lo persiste en base de datos de manera atómica.

        POR QUÉ:
            Garantiza que ningún archivo inválido, sobredimensionado o con extensión
            no permitida eluda las reglas del modelo cuando se interactúa desde la
            capa de servicios o comandos CLI sin formularios HTML.

        CÓMO:
            1. Instancia la entidad ImageAsset con los parámetros provistos.
            2. Auto-completa name y alt_text por defecto si vienen vacíos.
            3. Ejecuta full_clean() para disparar los validadores de campo (validate_image_file, FileExtensionValidator).
            4. Persiste con save() dentro de un bloque transaction.atomic().
            5. El procesamiento WebP asíncrono se delega automáticamente a Celery vía post_save (on_commit).

        Args:
            file: Archivo de imagen (InMemoryUploadedFile, SimpleUploadedFile o File).
            image_type: Categoría del activo (Product, Category, Carousel, Banner, etc.).
            name: Nombre identificatorio legible (opcional, extraído del nombre del archivo si es vacío).
            alt_text: Descripción de accesibilidad y SEO (opcional).

        Returns:
            Instancia de ImageAsset persistida y validada.

        Raises:
            django.core.exceptions.ValidationError: Si el archivo o los metadatos fallan la validación.
        """
        image_asset = ImageAsset(
            file=file,
            image_type=image_type,
            name=name or '',
            alt_text=alt_text or ''
        )

        with transaction.atomic():
            # REGLA: Ejecutar siempre full_clean() en servicios antes de save()
            image_asset.full_clean()
            image_asset.save()

        return image_asset

    @staticmethod
    def get_images_by_type(image_type: str) -> QuerySet[ImageAsset]:
        """
        Obtiene el queryset ordenado de imágenes filtradas por tipo.

        Args:
            image_type: Identificador del ImageType a consultar.

        Returns:
            QuerySet ordenado cronológicamente (más recientes primero).
        """
        return ImageAsset.objects.filter(image_type=image_type).order_by('-uploaded_at')

    @staticmethod
    def get_all_images() -> QuerySet[ImageAsset]:
        """
        Obtiene el queryset completo de todas las imágenes registradas en el banco.

        Returns:
            QuerySet ordenado cronológicamente (más recientes primero).
        """
        return ImageAsset.objects.all().order_by('-uploaded_at')

"""Media Bank Models"""
import os
from django.db import models
from media_bank.upload_utils import overwrite_upload_path


class ImageType(models.TextChoices):
    """Tipos de imagen en el banco."""
    PRODUCT = 'product', 'Producto'
    CATEGORY = 'category', 'Categoría'
    SUBCATEGORY = 'subcategory', 'Subcategoría'
    CAROUSEL = 'carousel', 'Carrusel'
    BANNER = 'banner', 'Banner'


# Mapa de rutas por tipo de imagen
UPLOAD_PATHS = {
    'product': 'photos/products/original/',
    'category': 'photos/categories/',
    'subcategory': 'photos/categories/subcategories/',
    'carousel': 'photos/carousel/',
    'banner': 'photos/banners/',
}


def image_asset_upload_path(instance, filename):
    """Rutea la imagen al directorio correcto según su tipo y sobrescribe."""
    base_path = UPLOAD_PATHS.get(instance.image_type, 'photos/products/original/')
    return overwrite_upload_path(f'{base_path}{filename}')


class ImageAsset(models.Model):
    """Imagen centralizada del banco de imágenes."""
    image_type = models.CharField(
        max_length=20,
        choices=ImageType.choices,
        default=ImageType.PRODUCT,
        help_text="Tipo de imagen"
    )
    file = models.ImageField(
        upload_to=image_asset_upload_path,
        help_text="Archivo de imagen"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nombre descriptivo (auto-generado del archivo si vacío)"
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Texto alternativo para SEO"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Imagen"
        verbose_name_plural = "Banco de Imágenes"

    def save(self, *args, **kwargs):
        if not self.name and self.file:
            self.name = os.path.splitext(os.path.basename(self.file.name))[0]
        if not self.alt_text and self.name:
            self.alt_text = f"{self.name} - Bulonera Alvear"
        super().save(*args, **kwargs)

    def get_seo_alt_text(self, context_name: str = '') -> str:
        """Retorna un texto alternativo contextualizado para SEO."""
        if context_name:
            return f"{context_name} - Bulonera Alvear Resistencia"
        return self.alt_text or f"{self.name} - Bulonera Alvear Resistencia"

    def get_geo_summary(self) -> str:
        """Genera un resumen estructurado en Markdown de la imagen para citación por LLMs."""
        url = self.get_webp_url() or self.image_url
        return (
            f"### Imagen Asset: {self.name}\n"
            f"- **Tipo:** {self.get_image_type_display()}\n"
            f"- **Alt Text:** {self.alt_text or self.name}\n"
            f"- **URL WebP/Optimizado:** {url}\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una respuesta fluida para lectura por asistentes de voz (AEO)."""
        return f"Imagen {self.name} de {self.get_image_type_display().lower()} en Bulonera Alvear."

    def get_schema_data(self, site_url: str = '') -> dict:
        """Retorna una representación formateada para Schema.org ImageObject."""
        url = f"{site_url}{self.image_url}" if site_url and not self.image_url.startswith('http') else self.image_url
        return {
            "@type": "ImageObject",
            "name": self.name,
            "caption": self.alt_text or self.name,
            "contentUrl": url,
        }

    def __str__(self):
        return self.name or str(self.file)

    @property
    def image_url(self):
        """URL del archivo de imagen."""
        if self.file and self.file.name:
            return self.file.url
        return '/static/images/placeholder.png'

    @property
    def thumbnail_url(self):
        """URL del thumbnail para preview en admin."""
        if self.file and self.file.name:
            return self.file.url
        return '/static/images/placeholder.png'

    def get_webp_url(self):
        """
        Construye la URL al archivo WebP correspondiente.
        Verifica la existencia física del archivo con fallback a subcarpetas legacy.
        Retorna None si no existe.
        """
        if not self.file or not self.file.name:
            return None
        
        # Obtener el nombre del archivo sin extensión
        base_name = os.path.splitext(os.path.basename(self.file.name))[0]
        
        # Candidatos de rutas por tipo (nueva → legacy)
        WEBP_CANDIDATES = {
            ImageType.PRODUCT: [
                f'photos/products/webp/{base_name}.webp',  # Estándar nuevo
                f'photos/products/webp/lg/{base_name}.webp',  # Legacy servidor
            ],
            ImageType.CATEGORY: [
                f'photos/categories/webp/{base_name}.webp',
            ],
            ImageType.SUBCATEGORY: [
                f'photos/categories/subcategories/webp/{base_name}.webp',
            ],
            ImageType.CAROUSEL: [
                f'photos/carousel/webp/{base_name}.webp',
            ],
            ImageType.BANNER: [
                f'photos/banners/webp/{base_name}.webp',
            ],
        }
        
        from django.conf import settings
        candidates = WEBP_CANDIDATES.get(self.image_type, [])
        
        for candidate in candidates:
            full_path = os.path.join(settings.MEDIA_ROOT, candidate)
            if os.path.isfile(full_path):
                return f'/media/{candidate}'
        
        # Fallback defensivo: si no existe, intentar generar el WebP sincrónicamente
        try:
            from store.utils import (
                ImageProcessor,
                CarouselImageProcessor,
                BannerImageProcessor,
                CategoryImageProcessor
            )
            
            processor_map = {
                ImageType.PRODUCT: lambda: ImageProcessor(self.file.path).process_image(),
                ImageType.CAROUSEL: lambda: CarouselImageProcessor(self.file.path).process_image(),
                ImageType.BANNER: lambda: BannerImageProcessor(self.file.path).process_image(),
                ImageType.CATEGORY: lambda: CategoryImageProcessor(self.file.path).process_image(),
                ImageType.SUBCATEGORY: lambda: CategoryImageProcessor(self.file.path).process_image(is_subcategory=True),
            }
            
            processor_fn = processor_map.get(self.image_type)
            if processor_fn:
                processor_fn()
                # Volver a verificar la existencia del primer candidato (estándar nuevo)
                if candidates:
                    first_candidate = candidates[0]
                    full_path = os.path.join(settings.MEDIA_ROOT, first_candidate)
                    if os.path.isfile(full_path):
                        return f'/media/{first_candidate}'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generando WebP sincrónicamente en get_webp_url para asset {self.id}: {e}")
        
        return None

"""Media Bank Models"""
import os
from django.db import models


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
    """Rutea la imagen al directorio correcto según su tipo."""
    base_path = UPLOAD_PATHS.get(instance.image_type, 'photos/products/original/')
    return f'{base_path}{filename}'


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
        super().save(*args, **kwargs)

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
        Retorna None si no existe ruta definida para el tipo.
        """
        if not self.file or not self.file.name:
            return None
        
        # Obtener el nombre del archivo sin extensión
        base_name = os.path.splitext(os.path.basename(self.file.name))[0]
        
        # Rutas del WebP según el tipo de imagen
        WEBP_PATHS = {
            ImageType.PRODUCT:     f'/media/photos/products/webp/{base_name}.webp',
            ImageType.CAROUSEL:    f'/media/photos/carousel/webp/{base_name}.webp',
            ImageType.BANNER:      f'/media/photos/banners/webp/{base_name}.webp',
            ImageType.CATEGORY:    f'/media/photos/categories/webp/{base_name}.webp',
            ImageType.SUBCATEGORY: f'/media/photos/categories/subcategories/webp/{base_name}.webp',
        }
        
        return WEBP_PATHS.get(self.image_type, None)

from django.db import models
from django.urls import reverse
from media_bank.upload_utils import overwrite_upload_path, create_clean_filename
import os

def category_image_path(instance, filename):
    clean_name = create_clean_filename(filename)
    relative_path = f'photos/categories/{clean_name}'
    return overwrite_upload_path(relative_path)

def subcategory_image_path(instance, filename):
    clean_name = create_clean_filename(filename)
    relative_path = f'photos/categories/subcategories/{clean_name}'
    return overwrite_upload_path(relative_path)

class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    slug = models.CharField(max_length=100, unique=True)
    # SEO Metadata fields (FASE 1.3 — Auditoría SEO)
    meta_title = models.CharField(max_length=70, blank=True, null=True, help_text="SEO Title (máx 70 caracteres)")
    meta_description = models.TextField(max_length=160, blank=True, null=True, help_text="SEO Description (máx 160 caracteres)")
    rich_description = models.TextField(
        "Descripción SEO Maestra",
        blank=True,
        help_text=(
            "Texto HTML para SEO de categoría. Incluir: tabla de medidas, "
            "aplicaciones, keywords long-tail. Ejemplo: 'Nuestros bulones G5 "
            "están disponibles en medidas desde 1/4 hasta 1.1/2 pulgadas...'"
        )
    )
    # Nuevo FK a ImageAsset (Fase A)
    image = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='categories',
        help_text="Imagen de categoría (desde Banco de Imágenes)"
    )
    # Legacy (Fase A - mantener para compatibilidad)
    cat_image = models.ImageField(upload_to=category_image_path, blank=True)

    
    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def save(self, *args, **kwargs):
        # Auto-fill meta_title si está vacío (FASE 1.3)
        if not self.meta_title:
            self.meta_title = f"Comprar {self.category_name} en Resistencia | Stock | Bulonera Alvear"[:70]
        # Auto-fill meta_description si está vacío (FASE 1.3)
        if not self.meta_description:
            if self.description:
                self.meta_description = f"{self.description} Stock real en Bulonera Alvear, Resistencia, Chaco."[:160]
            else:
                self.meta_description = f"¿Buscás {self.category_name.lower()} en Resistencia, Chaco? Stock real en Bulonera Alvear. Envíos al NEA/NOA y a toda Argentina."[:160]
        super().save(*args, **kwargs)
    
    def get_url(self):
        return reverse('store:products_by_category', args=[self.slug])
    
    @property
    def image_url(self):
        """Retorna la URL de la imagen de la categoría o un placeholder genérico."""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image and self.image.file and self.image.file.name:
            return self.image.file.url
        if self.cat_image and self.cat_image.name:
            return self.cat_image.url
        return '/static/images/placeholder.png'
    
    @property
    def webp_url(self):
        """Retorna URL del WebP de la categoría, o None si no existe."""
        if self.image and self.image.file:
            return self.image.get_webp_url()
        if self.cat_image and self.cat_image.name:
            base_name = os.path.splitext(os.path.basename(self.cat_image.name))[0]
            from django.conf import settings
            candidate = os.path.join(
                settings.MEDIA_ROOT, 
                'photos', 'categories', 'webp', 
                f'{base_name}.webp'
            )
            if os.path.isfile(candidate):
                return f'/media/photos/categories/webp/{base_name}.webp'
        return None
    
    def __str__(self):
        return self.category_name

class SubCategory(models.Model):
    subcategory_name = models.CharField(max_length=50, unique=True)
    slug = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    # SEO Metadata fields (FASE 1.3 — Auditoría SEO)
    meta_title = models.CharField(max_length=70, blank=True, null=True, help_text="SEO Title (máx 70 caracteres)")
    meta_description = models.TextField(max_length=160, blank=True, null=True, help_text="SEO Description (máx 160 caracteres)")
    rich_description = models.TextField(
        "Descripción SEO Maestra",
        blank=True,
        help_text="Texto HTML para SEO de subcategoría."
    )
    # Nuevo FK a ImageAsset (Fase A)
    image_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='subcategories',
        help_text="Imagen de subcategoría (desde Banco de Imágenes)"
    )
    # Legacy (Fase A - mantener para compatibilidad)
    image = models.ImageField(upload_to=subcategory_image_path, blank=True)
    
    class Meta:
        verbose_name = 'Sub Category'
        verbose_name_plural = 'Sub Categories'
    
    def save(self, *args, **kwargs):
        # Auto-fill meta_title si está vacío (FASE 1.3)
        if not self.meta_title:
            self.meta_title = f"Comprar {self.subcategory_name} en Resistencia | Bulonera Alvear"[:70]
        # Auto-fill meta_description si está vacío (FASE 1.3)
        if not self.meta_description:
            self.meta_description = (
                f"¿Buscás {self.subcategory_name.lower()} en Chaco? En Bulonera Alvear, "
                f"tu ferretería industrial en Av. Alvear 1301, Resistencia. Envíos a toda Argentina."
            )[:160]
        super().save(*args, **kwargs)

    def get_faqs(self):
        """Obtener todas las FAQs activas de esta subcategoría"""
        return self.faqs.filter(is_active=True)

    @property
    def image_url(self):
        """Retorna la URL de la imagen de la subcategoría o un placeholder genérico."""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image_asset and self.image_asset.file and self.image_asset.file.name:
            return self.image_asset.file.url
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/placeholder.png'
    
    def get_url(self):
        return reverse('store:products_by_subcategory', args=[self.category.slug, self.slug])
    
    def __str__(self):
        return self.subcategory_name
    
class FeaturedCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['position']
        verbose_name = 'Categoría Destacada'
        verbose_name_plural = 'Categorías Destacadas'
    
    def __str__(self):
        return self.category.category_name


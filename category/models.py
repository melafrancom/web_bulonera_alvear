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
    
    def __str__(self):
        return self.category_name

class SubCategory(models.Model):
    subcategory_name = models.CharField(max_length=50, unique=True)
    slug = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
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


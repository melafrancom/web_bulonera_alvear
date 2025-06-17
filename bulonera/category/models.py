from django.db import models
from django.urls import reverse
import unidecode
import os


def category_image_path(instance, filename):
    # Limpia el nombre del archivo para eliminar caracteres problemáticos
    # Obtiene el nombre base sin extensión
    name, ext = os.path.splitext(filename)
    # Convierte acentos a caracteres sin acentos y reemplaza espacios con guiones
    clean_name = unidecode.unidecode(name).replace(' ', '-')
    # Crea la ruta de destino con el nombre limpio
    return f'photos/categories/{clean_name}{ext}'

def subcategory_image_path(instance, filename):
    # Limpia el nombre del archivo para eliminar caracteres problemáticos
    # Obtiene el nombre base sin extensión
    name, ext = os.path.splitext(filename)
    # Convierte acentos a caracteres sin acentos y reemplaza espacios con guiones
    clean_name = unidecode.unidecode(name).replace(' ', '-')
    # Crea la ruta de destino con el nombre limpio
    return f'photos/categories/subcategories/{clean_name}{ext}'

class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    slug = models.CharField(max_length=100, unique=True)
    cat_image = models.ImageField(upload_to=category_image_path, blank=True)

    
    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def get_url(self):
        return reverse('products_by_category', args=[self.slug])
    
    def __str__(self):
        return self.category_name

class SubCategory(models.Model):
    subcategory_name = models.CharField(max_length=50, unique=True)
    slug = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    image = models.ImageField(upload_to=subcategory_image_path, blank=True)
    
    class Meta:
        verbose_name = 'Sub Category'
        verbose_name_plural = 'Sub Categories'
    
    def get_url(self):
        return reverse('products_by_subcategory', args=[self.category.slug, self.slug])
    
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


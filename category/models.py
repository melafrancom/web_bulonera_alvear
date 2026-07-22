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
        # Auto-fill meta_title si está vacío (límite estricto SERP: 60 caracteres)
        if not self.meta_title:
            self.meta_title = f"{self.category_name} en Resistencia | Bulonera Alvear"[:60]
        # Auto-fill meta_description si está vacío (FASE 1.3)
        if not self.meta_description:
            if self.description:
                self.meta_description = f"{self.description} Stock real en Bulonera Alvear, Resistencia, Chaco."[:160]
            else:
                self.meta_description = f"¿Buscás {self.category_name.lower()} en Resistencia, Chaco? Stock real en Bulonera Alvear. Envíos al NEA/NOA y a toda Argentina."[:160]
        super().save(*args, **kwargs)
    
    def get_url(self):
        return reverse('store:products_by_category', args=[self.slug])

    def get_seo_title(self) -> str:
        """
        Retorna el meta_title si existe (limitado a 60 chars). De lo contrario, genera 
        un título localizado limitado a un máximo estricto de 60 caracteres.
        """
        if self.meta_title:
            return self.meta_title[:60]
        
        base = f"{self.category_name} en Resistencia"
        suffix = " ❘ Bulonera Alvear"
        max_base = 60 - len(suffix)
        
        if len(base) > max_base:
            base = base[:max_base-1] + "…"
            
        return (base + suffix)[:60]

    def get_geo_summary(self) -> str:
        """Genera un resumen en Markdown estructurado para ingesta por LLMs (ChatGPT, Gemini, Perplexity)."""
        subcats = ", ".join([s.subcategory_name for s in self.subcategories.all()]) or "Productos y suministros varios"
        desc = self.description or self.meta_description or f"Catálogo especializado de {self.category_name.lower()}."
        return (
            f"### Categoría: {self.category_name}\n"
            f"- **Ubicación y Stock:** Resistencia, Chaco (Bulonera Alvear - Av. Alvear 1301)\n"
            f"- **Subcategorías en Stock:** {subcats}\n"
            f"- **Resumen:** {desc}\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una respuesta fluida en lenguaje natural para asistentes de voz (AEO)."""
        return f"En Bulonera Alvear contamos con la línea completa de {self.category_name} en Resistencia, Chaco, con stock permanente y envíos a todo el Nordeste Argentino."
    
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
        # Auto-fill meta_title si está vacío (límite estricto SERP: 60 caracteres)
        if not self.meta_title:
            self.meta_title = f"{self.subcategory_name} en Resistencia | Bulonera Alvear"[:60]
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

    def get_seo_title(self) -> str:
        """
        Retorna el meta_title si existe (limitado a 60 chars). De lo contrario, genera 
        un título localizado limitado a un máximo estricto de 60 caracteres.
        """
        if self.meta_title:
            return self.meta_title[:60]
        
        base = f"{self.subcategory_name} en Resistencia"
        suffix = " ❘ Bulonera Alvear"
        max_base = 60 - len(suffix)
        
        if len(base) > max_base:
            base = base[:max_base-1] + "…"
            
        return (base + suffix)[:60]

    def get_geo_summary(self) -> str:
        """Genera un resumen en Markdown estructurado para ingesta por LLMs (ChatGPT, Gemini, Perplexity)."""
        cat_name = self.category.category_name if self.category else "General"
        return (
            f"### Subcategoría: {self.subcategory_name} ({cat_name})\n"
            f"- **Ubicación y Stock:** Resistencia, Chaco (Bulonera Alvear)\n"
            f"- **Descripción:** {self.meta_description or self.subcategory_name}\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una respuesta fluida en lenguaje natural para asistentes de voz (AEO)."""
        cat_name = self.category.category_name if self.category else "general"
        return f"Bulonera Alvear ofrece la línea de {self.subcategory_name} dentro de la categoría {cat_name} en Resistencia, Chaco."
    
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


class NavbarItem(models.Model):
    """Item configurable para la barra de navegación (Capa 3)."""
    
    ITEM_TYPE_CHOICES = [
        ('category', 'Categoría del sistema'),
        ('custom', 'Link personalizado'),
        ('mega_menu', 'Mega-menú de categorías'),
    ]
    
    label = models.CharField(max_length=60)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='navbar_items',
        help_text="Solo si el tipo es 'Categoría del sistema'"
    )
    custom_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Solo si el tipo es 'Link personalizado' (ej: /blog/ o URL completa)"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Nombre de icono Lucide (ej: 'newspaper')"
    )
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    open_new_tab = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['position']
        verbose_name = 'Item de Navegación'
        verbose_name_plural = 'Items de Navegación'
        
    def __str__(self):
        return f"{self.label} ({self.get_item_type_display()})"
        
    def get_url(self):
        if self.item_type == 'category' and self.category:
            return self.category.get_url()
        elif self.item_type == 'custom':
            return self.custom_url
        return '#'



from django.db import models
from django.urls import reverse
from django.db.models import Avg, Count
from django.utils.text import slugify
from django.utils.text import Truncator
from django.conf import settings

SITE_URL = settings.SITE_URL
CURRENCY = settings.CURRENCY
#Local:
from account.models import Account
from category.models import Category, SubCategory
from .utils import ImageProcessor
from .utils import CarouselImageProcessor
import os
from media_bank.upload_utils import overwrite_upload_path, create_clean_filename

def store_product_image_path(instance, filename):
    clean_name = create_clean_filename(filename)
    return overwrite_upload_path(f'photos/products/{clean_name}')

def store_carousel_image_path(instance, filename):
    clean_name = create_clean_filename(filename)
    return overwrite_upload_path(f'photos/carousel/{clean_name}')

def store_banner_image_path(instance, filename):
    clean_name = create_clean_filename(filename)
    return overwrite_upload_path(f'photos/banners/{clean_name}')

# Create your models here.
# Modelo relacionado a todo sobre el producto. Con respecto a agregar/quitar productos al carrito está en 'cart'.

class Product(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200, unique=True)
    diameter = models.CharField(max_length=50, blank=True, null=True)
    length = models.CharField(max_length=50, blank=True, null=True)
    slug = models.CharField(max_length=200, unique=True)
    description = models.TextField(max_length=1500, blank=True)
    # Nuevo FK a ImageAsset (Fase A)
    image = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='products',
        help_text="Imagen principal del producto (desde Banco de Imágenes)"
    )
    # Legacy (Fase A - mantener para compatibilidad)
    images = models.ImageField(blank=True, upload_to=store_product_image_path)
    image_alt = models.CharField(max_length=255, blank=True, help_text="Texto alternativo de la imagen principal (SEO)")
    price = models.FloatField()
    stock = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategories = models.ManyToManyField(SubCategory, blank=True) # Relación ManyToMany con SubCategory
    is_available = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)#Útil para sitemap
    modified_date = models.DateTimeField(auto_now=True)#Útil para sitemap
    sold_count = models.IntegerField(default=0)
    #offers
    is_on_sale = models.BooleanField(default=False, verbose_name="En oferta")
    sale_price = models.FloatField(blank=True, null=True, verbose_name="Precio de oferta")
    discount_percentage = models.IntegerField(blank=True, null=True, verbose_name="Porcentaje de descuento")
    # Nuevos campos para META PIXEL y Google Merchant
    brand = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=20, choices=[
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('refurbished', 'Reacondicionado')
    ], default='new')
    gtin = models.CharField(max_length=50, blank=True, null=True)
    mpn = models.CharField(max_length=50, blank=True, null=True)
    google_category = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Categoría de Google Merchant (ej: Hardware > Fasteners > Bolts)"
    )
    
    # Funcionalidad del SEO
    meta_title = models.CharField("Meta título", max_length=70, blank=True, null=True)
    meta_description = models.TextField("Meta descripción", max_length=160, blank=True, null=True)
    meta_keywords = models.CharField("Palabras clave (separadas por comas)", max_length=255, blank=True, null=True)
    
    #Especificaciones del producto (opcional)
    norm = models.CharField("Norma", max_length=100, blank=True, null=True)
    grade = models.CharField("Grado/Dureza", max_length=100, blank=True, null=True)
    material = models.CharField("Material", max_length=100, blank=True, null=True)
    colour = models.CharField("Color", max_length=100, blank=True, null=True)
    type = models.CharField("Tipo", max_length=100, blank=True, null=True)
    form = models.CharField("Forma", max_length=100, blank=True, null=True)
    thread_formats = models.CharField("Formatos de rosca", max_length=100, blank=True, null=True)
    origin = models.CharField("Origen", max_length=100, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Auto-generar nombre completo y slug
        if self.diameter and self.length:
            # Si el nombre no incluye ya las dimensiones, agregarlas
            if f" {self.diameter} x {self.length}" not in self.name:
                self.name = f"{self.name} {self.diameter} x {self.length}"
        
        if not self.slug:
            self.slug = slugify(self.name)
            
            # Calcular el porcentaje de descuento si hay precio de oferta
        if self.is_on_sale and self.sale_price is not None and self.price > 0:
            self.discount_percentage = int(((self.price - self.sale_price) / self.price) * 100)
        else:
            self.discount_percentage = None
            
        if not self.meta_title:
            self.meta_title = self.name

        if not self.meta_description and hasattr(self, 'description'):
            self.meta_description = Truncator(self.description).chars(150)
            
        if not self.meta_keywords and self.name:
            self.meta_keywords = ', '.join(self.name.lower().split())
        # Guardar primero para tener el ID si es nuevo
        super().save(*args, **kwargs)
        
        # Procesar la imagen de forma asincrónica usando Celery
        if self.images:
            from store.tasks import process_product_image
            # Lanzar tarea asincrónica en background
            process_product_image.delay(self.id, self.images.path)
        
    def get_url(self):
        return reverse('store:product_detail', args=[self.category.slug, self.slug])
    
    def get_absolute_url(self):
    #URL completa para META PIXEL y Google Merchant
        return self.get_url()

    def __str__(self):
        return self.name
    
    def averageReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(average=Avg('rating'))
        avg = 0
        if reviews['average'] is not None:
            avg = float(reviews['average'])
        return avg
    
    def countReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(count=Count('id'))
        count = 0
        if reviews['count'] is not None:
            count = int(reviews['count'])
        return count
    
    @property
    def image_url(self):
        """Retorna la URL de la imagen principal o un placeholder genérico."""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image and self.image.file and self.image.file.name:
            return self.image.file.url
        if self.images and self.images.name:
            return self.images.url
        return '/static/images/placeholder.png'
    
        # Métodos específicos para META PIXEL
    def get_meta_pixel_data(self):
        return {
            'id': str(self.code),  # Usar el código del producto como ID
            'title': self.name,
            'description': self.description,
            'availability': 'in stock' if self.is_available and self.stock > 0 else 'out of stock',
            'condition': self.condition,
            'price': f"{self.price:.2f}",
            'link': f"{SITE_URL}{self.get_absolute_url()}",
            'image_link': f"{SITE_URL}{self.image_url}",
            'brand': self.brand if self.brand else "Bulonera Alvear",
        }
    
    # Métodos específicos para Google Merchant
    def get_merchant_data(self):
        # Generar product_type desde subcategorías
        subcats = self.subcategories.all()
        product_type = ' > '.join([sc.subcategory_name for sc in subcats]) if subcats.exists() else self.category.category_name
        
        return {
            'title': self.name,
            'description': self.description,
            'link': f"{SITE_URL}{self.get_absolute_url()}",
            'image_link': f"{SITE_URL}{self.image_url}",
            'availability': 'in stock' if self.is_available and self.stock > 0 else 'out of stock',
            'price': f"{self.price:.2f} {CURRENCY}",
            'brand': self.brand if self.brand else "Bulonera Alvear",
            'condition': self.condition,
            'gtin': self.gtin or '',  # Puedes agregar un campo para esto si es necesario // GTIN (Global Trade Item Number): es un código universal como el EAN, UPC o ISBN.
            'mpn': self.mpn or '',   # Puedes agregar un campo para esto si es necesario // MPN (Manufacturer Part Number): es un número de parte del fabricante, usado cuando no hay GTIN.
            'google_product_category': self.google_category if self.google_category else self.category.category_name,
            'product_type': product_type,  # Nueva línea
        }
    
    @property
    def get_image_urls(self):
        """Obtiene todas las URLs de las diferentes versiones de la imagen"""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image and self.image.file and self.image.file.name:
            webp_url = self.image.get_webp_url()
            if webp_url:
                return webp_url
        if self.images:
            base_name = os.path.splitext(os.path.basename(self.images.name))[0]
            extension = os.path.splitext(self.images.name)[1]
            return ImageProcessor.get_image_urls(base_name, extension)
        return '/static/images/placeholder.png'
    
    @property
    def webp_image_url(self):
        """Obtiene la URL del WebP generado para la imagen principal."""
        if self.image and self.image.file and self.image.file.name:
            return self.image.get_webp_url()
        if self.images:
            base_name = os.path.splitext(os.path.basename(self.images.name))[0]
            return f"/media/photos/products/webp/{base_name}.webp"
        return '/static/images/placeholder.png'
    
    # Métodos para obtener las dimensiones disponibles para el producto
    def get_dimension_variants(self):
        """Obtiene todas las variantes de dimensiones para este producto"""
        if not self.name:
            return Product.objects.none()
            
        # Obtener el nombre base
        base_name = self.get_base_name()
            
        # Buscar productos con el mismo nombre base y que compartan al menos una subcategoría
        variants = Product.objects.filter(
            category=self.category,
            subcategories__in=self.subcategories.all()
        ).distinct().exclude(id=self.id)
        
        # Filtrar variantes que tienen el mismo nombre base
        return [v for v in variants if v.get_base_name() == base_name]

    def get_available_dimensions(self):
        """Obtiene las dimensiones disponibles para este producto"""
        if not self.name:
            return None
            
        # Obtener variantes
        variants = list(self.get_dimension_variants())
        
        # Incluir el producto actual en la lista de variantes
        variants.append(self)
        
        # Recopilar dimensiones únicas
        diameters = sorted(list(set(v.diameter for v in variants if v.diameter)))
        lengths = sorted(list(set(v.length for v in variants if v.length)))
        
        return {
            'diameters': diameters,
            'lengths': lengths,
            'current_diameter': self.diameter,
            'current_length': self.length
        } if diameters and lengths else None
        
    def get_base_name(self):
        """Obtiene el nombre base del producto sin dimensiones"""
        if self.diameter and self.length:
            # Remover las dimensiones del nombre
            suffix = f" {self.diameter} x {self.length}"
            if self.name.endswith(suffix):
                return self.name[:-len(suffix)]
        return self.name

#Variaciones de productos:
class VariationManager(models.Manager):
    def color(self):
        return super(VariationManager, self).filter(variation_category='color', is_active=True)
    
    def tallas(self):
        return super(VariationManager, self).filter(variation_category='talla', is_active=True)
    
variation_category_choise = (
    ('color', 'color'),
    ('talla', 'talla'),
)

class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100, choices=variation_category_choise)
    variation_value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now=True)
    
    objects = VariationManager()
    
    def __str__(self):
        return self.variation_category + ' : ' + self.variation_value


class ReviewRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, blank=True)
    review = models.CharField(max_length=500, blank=True)
    rating = models.FloatField()
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject

class ProductGallery(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, default=None)
    # Nuevo FK a ImageAsset (Fase A)
    image_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='gallery_items',
        help_text="Imagen de galería (desde Banco de Imágenes)"
    )
    # Legacy (Fase A - mantener para compatibilidad)
    image = models.ImageField(upload_to=store_product_image_path, max_length=250)
    alt = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.product.name   

    @property
    def get_image_urls(self):
        """Devuelve las URLs principales de la imagen de galería"""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image_asset and self.image_asset.file and self.image_asset.file.name:
            webp_url = self.image_asset.get_webp_url()
            if webp_url:
                return {
                    'webp': webp_url,
                    'thumbnail': webp_url,
                }
        if self.image:
            base_name = os.path.splitext(os.path.basename(self.image.name))[0]
            extension = os.path.splitext(self.image.name)[1]
            urls = ImageProcessor.get_image_urls(base_name, extension)
            return {
                'webp': f"/media/{urls['webp']}",
                'thumbnail': f"/media/{urls['webp']}",
            }
        return {
            'webp': '/static/admin/img/placeholder.png',
            'thumbnail': '/static/admin/img/placeholder.png',
        }

#NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:

#CARRUSEL DE IMAGENES en la página 'home':
class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    show_title = models.BooleanField(
        default=True,
        help_text="¿Mostrar el título y fondo oscuro sobre la imagen? (Desactivar si la imagen ya tiene el texto dibujado)"
    )
    # Nuevo FK a ImageAsset (Fase A)
    image_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='carousel_items',
        help_text="Imagen del carrusel (desde Banco de Imágenes)"
    )
    # Art Direction: Mobile image asset (Fase 10)
    image_mobile_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='carousel_items_mobile',
        help_text="Imagen para mobile (Art Direction). Opcional."
    )
    # Art Direction: Tablet image asset (Fase 10 - Step 2)
    image_tablet_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='carousel_items_tablet',
        help_text="Imagen Tablet (640–1023px) desde el Banco. Opcional."
    )
    # Art Direction: Large image asset (Fase 10 - Step 2)
    image_large_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='carousel_items_large',
        help_text="Imagen Monitor Grande (≥1536px) desde el Banco. Opcional."
    )
    # Legacy (Fase A - mantener para compatibilidad)
    image = models.ImageField(
        upload_to=store_carousel_image_path,
        blank=True,
        null=True,
        help_text="Imagen directa (legacy). Usar 'Imagen del banco' es preferible."
    )
    # Legacy mobile field (Fase 10 - mantener para compatibilidad)
    image_mobile = models.ImageField(
        upload_to=store_carousel_image_path,
        blank=True,
        null=True,
        help_text="Imagen mobile directa (legacy). Usar Banco de Imágenes preferentemente."
    )
    description = models.TextField(blank=True, help_text="Descripción de la imagen (opcional)")
    url = models.CharField(max_length=255, blank=True, null=True, help_text="URL a la que redirige al hacer clic")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True, 
                            help_text="Asociar con un producto (opcional)")
    position = models.PositiveIntegerField(default=0, help_text="Orden de aparición")
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['position']
        verbose_name = "Imagen del Carrusel"
        verbose_name_plural = "Imágenes del Carrusel"
    
    def __str__(self):
        return self.title if self.title else str(self.image)

    def save(self, *args, **kwargs):
        # Guardar primero para tener el ID si es nuevo
        super().save(*args, **kwargs)
        
        # Procesar la imagen de forma asincrónica usando Celery (solo si existe archivo físico)
        if self.image and self.image.name:
            from store.tasks import process_carousel_image
            # Lanzar tarea asincrónica en background
            process_carousel_image.delay(self.id, self.image.path)

    @property
    def get_image_urls(self):
        """Obtiene todas las URLs de las diferentes versiones de la imagen"""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image_asset and self.image_asset.file and self.image_asset.file.name:
            webp_url = self.image_asset.get_webp_url()
            if webp_url:
                return webp_url
        if self.image:
            base_name = os.path.splitext(os.path.basename(self.image.name))[0]
            return CarouselImageProcessor.get_image_urls(base_name)
        return None

    @property
    def webp_image_url(self):
        """Obtiene la URL de la versión WebP de la imagen del carrusel."""
        if self.image_asset and self.image_asset.file and self.image_asset.file.name:
            return self.image_asset.get_webp_url()
        if self.image and self.image.name:
            base_name = os.path.splitext(os.path.basename(self.image.name))[0]
            return f"/media/photos/carousel/webp/{base_name}.webp"
        return '/static/images/placeholder.png'

    @property
    def image_url(self):
        """Retorna la URL de la imagen del carrusel o un placeholder genérico."""
        # Fase A: Intentar FK primero, fallback a legacy
        if self.image_asset and self.image_asset.file and self.image_asset.file.name:
            return self.image_asset.file.url
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/placeholder.png'

    @property
    def mobile_image_url(self):
        """Retorna la URL de la imagen móvil para Art Direction (Fase 10)."""
        # Prioridad: image_mobile_asset > image_mobile > image_url (fallback)
        if self.image_mobile_asset and self.image_mobile_asset.file and self.image_mobile_asset.file.name:
            return self.image_mobile_asset.file.url
        if self.image_mobile and self.image_mobile.name:
            return self.image_mobile.url
        # Fallback a imagen desktop si no hay móvil específica
        return self.image_url

    @property
    def tablet_image_url(self):
        """URL de imagen para tablet (640–1023px) con fallback a desktop."""
        if self.image_tablet_asset and self.image_tablet_asset.file and self.image_tablet_asset.file.name:
            return self.image_tablet_asset.file.url
        return self.image_url

    @property
    def large_image_url(self):
        """URL de imagen para monitores grandes (≥1536px) con fallback a desktop."""
        if self.image_large_asset and self.image_large_asset.file and self.image_large_asset.file.name:
            return self.image_large_asset.file.url
        return self.image_url

    @property
    def tablet_webp_url(self):
        """URL WebP para tablet con fallback a desktop WebP."""
        if self.image_tablet_asset and self.image_tablet_asset.file and self.image_tablet_asset.file.name:
            webp = self.image_tablet_asset.get_webp_url()
            if webp:
                return webp
        return self.webp_image_url

    @property
    def large_webp_url(self):
        """URL WebP para monitors grandes con fallback a desktop WebP."""
        if self.image_large_asset and self.image_large_asset.file and self.image_large_asset.file.name:
            webp = self.image_large_asset.get_webp_url()
            if webp:
                return webp
        return self.webp_image_url

#NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:
#CREAMOS UN MODELO PARA RASTREAR LAS BUSQUEDAS MÁS BUSCADAS POR TODOS LOS USUARIOS
class ProductSearch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True)
    search_count = models.PositiveIntegerField(default=1)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Búsqueda de Producto"
        verbose_name_plural = "Búsquedas de Productos"
        unique_together = [['product', 'user'], ['product', 'session_key']]
    
    def __str__(self):
        return f"{self.product.name} - {self.search_count} búsquedas"

#NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:
#Creamos un modelo para FAQ (Preguntas Frecuentes)

class FAQCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.IntegerField(default=0, help_text="Orden de aparición en la lista")
    
    class Meta:
        ordering = ['order']
        verbose_name_plural = "FAQ Categories"
    
    def __str__(self):
        return self.name
    
class FAQ(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    subcategory = models.ForeignKey(
        'category.SubCategory', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='faqs'
    )
    order = models.IntegerField(default=0, help_text="Orden de aparición en la categoría")
    is_active = models.BooleanField(default=True, help_text="¿Está activa la pregunta frecuente?")
    
    class Meta:
        ordering = [ 'order']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        
    def __str__(self):
        return self.question


# ============================================================================
# HOME PAGE BUILDER — Secciones dinámicas + Banners intercalados
# ============================================================================

class HomeSection(models.Model):
    """
    Bloque dinámico de la Home. Controla qué se muestra, en qué orden,
    y si está activo o no. El admin reordena arrastrando posiciones.
    """
    SECTION_TYPES = [
        ('hero', 'Carrusel Hero (Banners Principales)'),
        ('quick_access', 'Acceso Rápido (Iconos: pagos, envíos, etc.)'),
        ('trust_bar', 'Barra de Confianza'),
        ('product_carousel', 'Carrusel de Productos'),
        ('banner_landing', 'Banner Landing (1 imagen ancho completo)'),
        ('banner_double', 'Banner Doble (2 imágenes lado a lado)'),
        ('banner_triple', 'Banner Triple (3 imágenes en fila)'),
        ('categories_featured', 'Grid de Categorías Destacadas'),
        ('categories_carousel', 'Carrusel de Categorías'),
        ('how_to_buy', 'Sección Cómo Comprar'),
    ]

    SOURCE_TYPES = [
        ('bestsellers', 'Más Vendidos'),
        ('most_searched', 'Más Buscados'),
        ('by_category', 'Por Categoría'),
        ('on_sale', 'En Oferta'),
        ('newest', 'Más Recientes'),
        ('custom', 'Selección Manual'),
        ('categories_featured', 'Categorías Destacadas'),
        ('categories_carousel', 'Carrusel de Categorías'),
    ]

    title = models.CharField(max_length=150,
        help_text="Título visible en la Home (ej: 'Los más vendidos')")
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES,
        blank=True, null=True,
        help_text="Fuente de productos (solo para carruseles de productos)")
    category = models.ForeignKey('category.Category',
        on_delete=models.SET_NULL, blank=True, null=True,
        help_text="Categoría fuente (solo si source_type = 'by_category')")
    max_products = models.PositiveSmallIntegerField(default=12,
        help_text="Cantidad máxima de productos a mostrar")
    position = models.PositiveSmallIntegerField(default=0,
        help_text="Orden de aparición (menor = más arriba)")
    is_active = models.BooleanField(default=True)
    # Estilo visual opcional
    highlight_color = models.CharField(max_length=30, blank=True,
        help_text="Color de fondo especial (ej: 'bg-amber-50' para ofertas). Dejar vacío = default.")

    class Meta:
        ordering = ['position']
        verbose_name = "Sección de la Home"
        verbose_name_plural = "Secciones de la Home"

    def __str__(self):
        return f"[{self.position}] {self.title} ({self.get_section_type_display()})"

    @property
    def has_manual_products(self):
        """True si el admin seleccionó productos manualmente."""
        return self.home_section_products.exists()


class HomeSectionProduct(models.Model):
    """
    Through model que permite al admin elegir exactamente qué productos aparecen
    en cada carrusel, y en qué orden.
    """
    section = models.ForeignKey(HomeSection, on_delete=models.CASCADE,
        related_name='home_section_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
        related_name='home_sections')
    position = models.PositiveSmallIntegerField(default=0,
        help_text="Orden dentro del carrusel")

    class Meta:
        ordering = ['position']
        unique_together = ['section', 'product']
        verbose_name = "Producto de la Sección"
        verbose_name_plural = "Productos de la Sección"

    def __str__(self):
        return f"{self.product.name} → {self.section.title}"


class PromoBanner(models.Model):
    """
    Banner promocional para secciones de tipo banner_*.
    Sistema de enlaces por prioridad: url > product > category.
    """
    section = models.ForeignKey(HomeSection, on_delete=models.CASCADE,
        related_name='banners')
    title = models.CharField(max_length=150, blank=True,
        help_text="Título interno (no visible al público)")
    alt_text = models.CharField(max_length=200, blank=True,
        help_text="Texto alternativo para SEO y accesibilidad")

    # === Imágenes responsive ===
    # Nuevos campos del Banco de Imágenes (Fase A+)
    image_desktop_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='promo_banners_desktop',
        help_text="Imagen Desktop desde el Banco"
    )
    image_mobile_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='promo_banners_mobile',
        help_text="Imagen Mobile desde el Banco (opcional)"
    )
    # Art Direction: Tablet image asset (Fase 10 - Step 2)
    image_tablet_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='promo_banners_tablet',
        help_text="Imagen Tablet (640–1023px) desde el Banco. Opcional."
    )
    # Art Direction: Large image asset (Fase 10 - Step 2)
    image_large_asset = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='promo_banners_large',
        help_text="Imagen Monitor Grande (≥1536px) desde el Banco. Opcional."
    )
    
    # Legacy ImageFields (mantener para compatibilidad)
    image_desktop = models.ImageField(upload_to=store_banner_image_path,
        blank=True, null=True,
        help_text="[LEGACY] Imagen para desktop (usar Banco de Imágenes preferentemente)")
    image_mobile = models.ImageField(upload_to=store_banner_image_path,
        blank=True, null=True,
        help_text="[LEGACY] Imagen para mobile (usar Banco de Imágenes preferentemente)")

    # === Sistema de enlaces híbrido ===
    # Prioridad: url > link_product > link_category
    url = models.CharField(max_length=500, blank=True,
        help_text="URL manual (máxima prioridad). Para blogs, redes sociales, páginas externas.")
    link_product = models.ForeignKey(Product,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name='promo_banners',
        help_text="Redirigir a este producto específico")
    link_category = models.ForeignKey('category.Category',
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name='promo_banners',
        help_text="Redirigir a la tienda filtrada por esta categoría")
    link_params = models.CharField(max_length=300, blank=True,
        help_text="Filtros adicionales para la URL. Ej: ?promo=active, ?brand=stanley")
    open_new_tab = models.BooleanField(default=False,
        help_text="Abrir en pestaña nueva (recomendado para enlaces externos)")

    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['position']
        verbose_name = "Banner Promocional"
        verbose_name_plural = "Banners Promocionales"

    def __str__(self):
        return self.title or f"Banner #{self.position} de {self.section.title}"

    def get_link_url(self):
        """
        Resuelve la URL final del banner según prioridad.
        1. URL manual (para externo: blog, Instagram, TikTok)
        2. Producto específico (ej: oferta de un producto)
        3. Categoría + filtros (ej: /tienda/pinturas/?promo=active)
        4. Sin enlace
        """
        if self.url:
            return self.url
        if self.link_product:
            return self.link_product.get_url()
        if self.link_category:
            base_url = self.link_category.get_url()
            if self.link_params:
                return f"{base_url}{self.link_params}"
            return base_url
        return None

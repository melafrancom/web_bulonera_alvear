from django.db import models
from django.urls import reverse
from django.db.models import Avg, Count
from django.utils.text import slugify
from django.utils.text import Truncator
from bulonera.settings import SITE_URL, CURRENCY
#Local:
from account.models import Account
from category.models import Category, SubCategory

# Create your models here.
# Modelo relacionado a todo sobre el producto. Con respecto a agregar/quitar productos al carrito está en 'cart'.

class Product(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200, unique=True)
    diameter = models.CharField(max_length=50, blank=True, null=True)
    length = models.CharField(max_length=50, blank=True, null=True)
    slug = models.CharField(max_length=200, unique=True)
    description = models.TextField(max_length=1500, blank=True)
    images = models.ImageField(blank=True, upload_to='photos/products')
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
    
    # Funcionalidad del SEO
    meta_title = models.CharField("Meta título", max_length=70, blank=True, null=True)
    meta_description = models.TextField("Meta descripción", max_length=160, blank=True, null=True)
    meta_keywords = models.CharField("Palabras clave (separadas por comas)", max_length=255, blank=True, null=True)
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
            
        super(Product, self).save(*args, **kwargs)
    
    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])
    
    def get_absolute_url(self):
    #URL completa para META PIXEL y Google Merchant
        return f"{SITE_URL}{self.get_url()}"

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
    
        # Métodos específicos para META PIXEL
    def get_meta_pixel_data(self):
        return {
            'id': str(self.id),
            'title': self.name,
            'description': self.description,
            'availability': 'in stock' if self.is_available and self.stock > 0 else 'out of stock',
            'condition': self.condition,
            'price': f"{self.price:.2f}",
            'link': self.get_absolute_url(),
            'image_link': f"{SITE_URL}{self.images.url}" if self.images else "",
            'brand': self.brand,
        }
    
    # Métodos específicos para Google Merchant
    def get_merchant_data(self):
        return {
            'title': self.name,
            'description': self.description,
            'link': self.get_absolute_url(),
            'image_link': f"{SITE_URL}{self.images.url}" if self.images else "",
            'availability': 'in stock' if self.is_available and self.stock > 0 else 'out of stock',
            'price': f"{self.price:.2f} {CURRENCY}",
            'brand': self.brand,
            'condition': self.condition,
            'gtin': '',  # Puedes agregar un campo para esto si es necesario // GTIN (Global Trade Item Number): es un código universal como el EAN, UPC o ISBN.
            'mpn': '',   # Puedes agregar un campo para esto si es necesario // MPN (Manufacturer Part Number): es un número de parte del fabricante, usado cuando no hay GTIN.
            'google_product_category': self.category.name,
        }
    
    # Deberíamos agregar imagenes, variaciones, reviews, etc...
    def get_image_url(self):
        if self.images:
            return self.images.url
        return '/static/images/placeholder.png'  # Imagen por defecto
    
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
    image = models.ImageField(upload_to='store/products', max_length=250)
    alt = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.product.name   


#NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:

#CARRUSEL DE IMAGENES en la página 'home':
class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='photos/carousel')
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

from django.db import models
from django.urls import reverse
from django.db.models import Avg, Count
from django.utils.text import slugify
from bulonera.settings import SITE_URL, CURRENCY
#Local:
from account.models import Account
from category.models import Category, SubCategory

# Create your models here.
# Modelo relacionado a todo sobre el producto. Con respecto a agregar/quitar productos al carrito está en 'cart'.

class Product(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200, unique=True)
    slug = models.CharField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    images = models.ImageField(blank=True, upload_to='photos/products')
    price = models.FloatField()
    stock = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategories = models.ManyToManyField(SubCategory, blank=True) # Relación ManyToMany con SubCategory
    is_available = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    # Nuevos campos para META PIXEL y Google Merchant
    brand = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=20, choices=[
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('refurbished', 'Reacondicionado')
    ], default='new')
    
    def save(self, *args, **kwargs):
    # Auto-generar slug si no se proporciona
        if not self.slug:
            self.slug = slugify(self.name)
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
            'gtin': '',  # Puedes agregar un campo para esto si es necesario
            'mpn': '',   # Puedes agregar un campo para esto si es necesario
            'google_product_category': self.category.name,
        }
    
#Deberíamos agregar imagenes, variaciones, reviews, etc...

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

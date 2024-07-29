from django.db import models
from django.contrib import admin
from category.models import Category
from django.urls import reverse
from account.models import Account
# Create your models here.
# Modelo relacionado a todo sobre el producto. Con respecto a agregar/quitar productos al carrito está en 'cart'.

class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.CharField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    images = models.ImageField(upload_to='photos/products')
    price = models.IntegerField()
    stock = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    def get_url(self):
        return reverse('product_detail', args=(self.category.slug, self.slug))
    
    def __str__(self):
        return self.name
    
    def averageReviews(self):
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
    
#Deberíamos agregar imagenes, variaciones, reviews, etc...

class VariationManager(models.Manager):
    pass

class Variation(models.Model):
    pass

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

class ProductGalleryInLine(admin.TabularInline):
    pass

class ProductAdmin(admin.ModelAdmin):
    pass

class VariationAdmin(admin.ModelAdmin):
    pass


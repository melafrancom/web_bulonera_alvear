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
    
#Deberíamos agregar imagenes, variaciones, reviews, etc...

class VariationManager(models.Manager):
    pass

class Variation(models.Model):
    pass

class ReviewRating(models.Model):
    pass

class ProductGallery(models.Model):
    pass

class ProductGalleryInLine(admin.TabularInline):
    pass

class ProductAdmin(admin.ModelAdmin):
    pass

class VariationAdmin(admin.ModelAdmin):
    pass


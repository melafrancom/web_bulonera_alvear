from django.contrib import admin
from django.db import models
from store.models import Product, Variation
from account.models import Account, UserProfile


# Create your models here.

#Crea un carrito. Imaginemos a cada carrito cómo único, y único para cada usuario. Pero que puede contener muchos productos, incluso en cantidad.
class Cart(models.Model):
    cart_id = models.CharField(max_length=250, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.cart_id
    

#Creamos los items de cada carrito, los cuales pueden ser muchos para cada carrito.
class CartItem(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)
    variation = models.ManyToManyField(Variation, blank=True)
    
    def subtotal(self):
        return self.product.price * self.quantity
    
    def __unicode__(self):
        return self.product
    


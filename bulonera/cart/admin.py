from django.contrib import admin
from .models import Cart, CartItem, CartAdmin, CartItemAdmin
# Register your models here.


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)

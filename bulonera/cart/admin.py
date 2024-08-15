from django.contrib import admin
from .models import Cart, CartItem
# Register your models here.


class CartAdmin(admin.ModelAdmin):
    list_display = ('cart_id', 'date_added') #Está propiedad 'list_display' define los campos a mostrar del modelo cart que se mostraran como columnas en la lista dentro de la administración.
    

class CartItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'cart', 'quantity', 'is_active') # Idem anterior.


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)

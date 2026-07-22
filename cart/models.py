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

    def get_geo_summary(self) -> str:
        """Genera un resumen estructurado del carrito para consumo del ecosistema."""
        items_count = self.cartitem_set.filter(is_active=True).count()
        return (
            f"### Carrito de Compras #{self.cart_id}\n"
            f"- **Artículos Activos:** {items_count}\n"
            f"- **Punto de Despacho:** Resistencia, Chaco\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una respuesta fluida para asistentes de voz (AEO)."""
        items_count = self.cartitem_set.filter(is_active=True).count()
        return f"Carrito de compras activo con {items_count} producto{'s' if items_count != 1 else ''} en Bulonera Alvear."


#Creamos los items de cada carrito, los cuales pueden ser muchos para cada carrito.
class CartItem(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)
    variation = models.ManyToManyField(Variation, blank=True)
    purchase_price = models.FloatField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
    # Set the purchase price based on whether product is on sale
        if not self.purchase_price:
            if self.product.is_on_sale and self.product.sale_price:
                self.purchase_price = self.product.sale_price
            else:
                self.purchase_price = self.product.price
        super(CartItem, self).save(*args, **kwargs)
    
    @property
    def sub_total(self):
        return self.purchase_price * self.quantity

    def get_geo_summary(self) -> str:
        """Genera un resumen estructurado del ítem del carrito."""
        product_name = self.product.product_name if self.product else 'Producto'
        return (
            f"### Ítem de Carrito: {product_name}\n"
            f"- **Cantidad:** {self.quantity}\n"
            f"- **Precio de Compra:** ${self.purchase_price or 0:.2f}\n"
            f"- **Subtotal:** ${self.sub_total:.2f}\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una descripción conversacional para lectura por voz."""
        product_name = self.product.product_name if self.product else 'Producto'
        return f"{self.quantity} unidad{'es' if self.quantity > 1 else ''} de {product_name} en el carrito."
    
    def __unicode__(self):
        return self.product
    


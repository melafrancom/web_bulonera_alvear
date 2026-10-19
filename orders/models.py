from django.db import models
from django.utils import timezone

from account.models import UserProfile, Account
from store.models import Product, Variation
from cart.models import CartItem


# Create your models here.

class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_id = models.CharField(max_length=100)
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id
    

class Order(models.Model):
    STATUS = (
        ('New', 'Nuevo'),
        ('Accepted', 'Aceptado'),
        ('Completed', 'Completado'),
        ('Cancelled', 'Cancelado'),
    )
    DELIVERY_CHOICES = (
        ('pickup', 'Retiro en Local (Av. Alvear 1301)'),
        ('shipping', 'Envío a convenir (Interior / NEA)'),
    )
    INVOICE_CHOICES = (
        ('B', 'Consumidor Final (Factura B)'),
        ('A', 'Responsable Inscripto (Factura A)'),
    )

    #### Datos de order ####
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    order_number = models.CharField(max_length=30, unique=True, db_index=True)
    order_note = models.CharField(max_length=100, blank=True)
    order_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS, default='New')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Modalidad de entrega e identificación fiscal
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='pickup', verbose_name='Modalidad de Entrega')
    invoice_type = models.CharField(max_length=10, choices=INVOICE_CHOICES, default='B', verbose_name='Tipo de Factura')
    doc_number = models.CharField(max_length=20, blank=True, verbose_name='DNI o CUIT')
    business_name = models.CharField(max_length=150, blank=True, verbose_name='Razón Social')

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=25)
    email = models.EmailField(max_length=50)
    address_line_1 = models.CharField(max_length=100, blank=True)
    address_line_2 = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=10, blank=True)  # Código postal argentino (4 dígitos o CPA de 8 caracteres)
    
    ip = models.CharField(max_length=25, blank=True)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        if self.delivery_type == 'pickup':
            return 'Retiro en Mostrador (Av. Alvear 1301, Resistencia)'
        return f'{self.address_line_1} {self.address_line_2}'.strip()

    def get_delivery_display_name(self) -> str:
        """Retorna el nombre descriptivo de la modalidad de entrega."""
        return dict(self.DELIVERY_CHOICES).get(self.delivery_type, self.delivery_type)

    def get_invoice_display_name(self) -> str:
        """Retorna el nombre descriptivo del tipo de factura."""
        return dict(self.INVOICE_CHOICES).get(self.invoice_type, self.invoice_type)

    def get_status_badge_class(self) -> str:
        """Retorna clases de Tailwind CSS para la insignia de estado del pedido."""
        badge_map = {
            'New': 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 border-blue-300',
            'Accepted': 'bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-200 border-amber-300',
            'Completed': 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 border-green-300',
            'Cancelled': 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 border-red-300',
        }
        return badge_map.get(self.status, 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200')

    def get_voice_summary(self) -> str:
        """Genera una respuesta en lenguaje natural para asistentes de voz (AEO)."""
        return f"Pedido #{self.order_number} en Bulonera Alvear. Estado actual: {self.get_status_display()}."

    def get_geo_summary(self) -> str:
        """Genera un resumen seguro en Markdown sin información personal sensible."""
        date_str = self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else 'Reciente'
        return (
            f"### Pedido #{self.order_number}\n"
            f"- **Estado:** {self.get_status_display()}\n"
            f"- **Origen/Despacho:** Bulonera Alvear (Av. Alvear 1301, Resistencia, Chaco)\n"
            f"- **Fecha:** {date_str}\n"
        )

    def __str__(self):
        return self.first_name
    
    
class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, blank=True, null=True)
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation = models.ManyToManyField(Variation, blank=True)
    quantity = models.IntegerField()
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product.name
    


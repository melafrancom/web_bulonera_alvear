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
        ('unspecified', 'No especificado (Histórico)'),
    )
    INVOICE_CHOICES = (
        ('B', 'Consumidor Final (Factura B)'),
        ('A', 'Responsable Inscripto (Factura A)'),
        ('unspecified', 'No especificado (Histórico)'),
    )

    #### Datos de order ####
    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    order_number = models.CharField(max_length=30, unique=True, db_index=True)
    order_note = models.CharField(max_length=100, blank=True)
    order_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS, default='New')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Modalidad de entrega e identificación fiscal
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='unspecified', verbose_name='Modalidad de Entrega')
    invoice_type = models.CharField(max_length=15, choices=INVOICE_CHOICES, default='unspecified', verbose_name='Tipo de Factura')
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
    
    # Evidencia legal de aceptación de Términos y Revocación Legal (Ley 24.240 y CCCN)
    terms_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Aceptación de Términos')
    terms_version = models.CharField(max_length=20, default='2026-10', blank=True, verbose_name='Versión de Términos Aceptada')
    
    
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self) -> str:
        """
        Retorna la representación textual de la dirección según la modalidad.
        Garantiza que una orden histórica (unspecified) no aparezca etiquetada como envío.
        """
        if self.delivery_type == 'pickup':
            return 'Retiro en Mostrador (Av. Alvear 1301, Resistencia)'
        elif self.delivery_type == 'shipping':
            addr = f'{self.address_line_1} {self.address_line_2}'.strip()
            return addr if addr else 'Dirección de envío no especificada'
        elif self.delivery_type == 'unspecified':
            addr = f'{self.address_line_1} {self.address_line_2}'.strip()
            return addr if addr else 'Modalidad no especificada (Orden histórica)'
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


class OrderRevocation(models.Model):
    """
    Modela las solicitudes de revocación legal (Botón de Arrepentimiento),
    conforme al Art. 34 de la Ley 24.240 y las Disposiciones 954/2025 y 3/2026.

    Reglas de diseño:
    - revocation_code es una referencia de gestión, inmutable y única (ARR-YYYYMMDD-XXXXXXXXXX).
    - Simplificación: contact_method y contact_value unificados.
    - Minimización de datos: NO persiste la dirección IP.
    - Auditoría de 24hs: registra canal de origen, acuse al cliente y medidas tomadas.
    """
    ORIGIN_CHOICES = (
        ('web', 'Formulario Web'),
        ('whatsapp', 'Atención Directa WhatsApp'),
    )

    METHOD_CHOICES = (
        ('whatsapp', 'WhatsApp / Teléfono'),
        ('email', 'Correo electrónico'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pendiente de Atención'),
        ('contacted', 'Contacto Iniciado'),
        ('in_review', 'En Evaluación Logística / Producto'),
        ('resolved', 'Revocación Efectivizada / Resuelta'),
        ('not_eligible_exception', 'No aplica: excepción legal verificada'),
        ('cancelled', 'Cancelada por el Cliente'),
    )

    # Código interno de gestión de la solicitud
    revocation_code = models.CharField(
        max_length=35,
        unique=True,
        db_index=True,
        verbose_name='Código de Revocación'
    )

    origin = models.CharField(
        max_length=15,
        choices=ORIGIN_CHOICES,
        default='web',
        verbose_name='Canal de Origen'
    )

    # Identificación básica (sin DNI obligatorio)
    customer_name = models.CharField(
        max_length=150,
        verbose_name='Nombre completo o Razón Social'
    )
    contact_method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default='whatsapp',
        verbose_name='Medio de Contacto'
    )
    contact_value = models.CharField(
        max_length=150,
        verbose_name='Teléfono o Correo según medio'
    )

    # Referencias comerciales opcionales
    order_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número de pedido o factura informado'
    )
    order = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revocations',
        verbose_name='Orden vinculada en sistema'
    )
    details = models.TextField(
        blank=True,
        verbose_name='Detalles o comentarios del consumidor'
    )

    exception_basis = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Excepción legal evaluada'
    )
    exception_reason = models.TextField(
        blank=True,
        verbose_name='Fundamento documentado de la excepción'
    )

    # Auditoría del cumplimiento legal de las 24 horas
    acknowledgment_sent = models.BooleanField(
        default=False,
        verbose_name='Acuse de código emitido al cliente'
    )
    acknowledgment_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/hora de emisión del acuse'
    )
    acknowledgment_channel = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Canal por el que se emitió el acuse'
    )
    acknowledged_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_revocations',
        verbose_name='Operador que envió el acuse manual'
    )
    measures_taken = models.BooleanField(
        default=False,
        verbose_name='Medidas operativas adoptadas (< 24hs)'
    )
    measures_description = models.TextField(
        blank=True,
        verbose_name='Descripción de las medidas operativas iniciadas'
    )
    measures_taken_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/hora de la primera medida operativa'
    )
    handled_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_revocations',
        verbose_name='Operador asignado'
    )
    contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/hora del primer contacto'
    )

    # Gestión de estados y resolución
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Estado'
    )
    internal_notes = models.TextField(
        blank=True,
        verbose_name='Notas internas de seguimiento'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de resolución')

    class Meta:
        verbose_name = 'Solicitud de Arrepentimiento'
        verbose_name_plural = 'Solicitudes de Arrepentimiento'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.revocation_code} — {self.customer_name} ({self.get_origin_display()})"

    


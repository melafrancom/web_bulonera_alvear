from django.db import models

# Create your models here.
class ContactOption(models.Model):
    CONTACT_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Correo Electrónico'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nombre")
    email = models.EmailField(verbose_name="Correo Electrónico")
    contact_method = models.CharField(max_length=10, choices=CONTACT_CHOICES, default='email', verbose_name="Método de Contacto")
    subject = models.CharField(max_length=200, verbose_name="Asunto")
    message = models.TextField(verbose_name="Mensaje")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Envío")
    
    class Meta:
        verbose_name = "Mensaje de Contacto"
        verbose_name_plural = "Mensajes de Contacto"
    
    def get_geo_summary(self) -> str:
        """Genera un resumen estructurado del mensaje de contacto para auditoría interna."""
        return (
            f"### Mensaje de Contacto #{self.id or 'Nuevo'}\n"
            f"- **De:** {self.name} ({self.email})\n"
            f"- **Canal:** {self.get_contact_method_display()}\n"
            f"- **Asunto:** {self.subject}\n"
        )

    def get_voice_summary(self) -> str:
        """Genera una respuesta fluida para lectura por voz."""
        return f"Mensaje de contacto de {self.name} sobre {self.subject} enviado a Bulonera Alvear."

    def __str__(self):
        return f"{self.name} - {self.subject}"

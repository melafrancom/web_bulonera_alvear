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
    
    def __str__(self):
        return f"{self.name} - {self.subject}"
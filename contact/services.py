"""
Contact App Services

Contiene la lógica de negocio pura para manejo de contactos.
"""
import logging
from django.core.mail import EmailMessage
from django.conf import settings

from .models import ContactOption

logger = logging.getLogger(__name__)


class ContactService:
    """Servicio para manejo de contactos y notificaciones"""
    
    @staticmethod
    def create_contact(name: str, email: str, contact_method: str, subject: str, message: str) -> ContactOption:
        """
        Crea un nuevo registro de contacto y procesa según el método elegido.
        
        Args:
            name: Nombre del contactante
            email: Email del contactante
            contact_method: Método de contacto ('email' o 'whatsapp')
            subject: Asunto del mensaje
            message: Cuerpo del mensaje
            
        Returns:
            ContactOption: Instancia guardada del contacto
            
        Raises:
            ValueError: Si los parámetros no son válidos
        """
        # Validar parámetros
        if not all([name, email, subject, message]):
            raise ValueError("Todos los campos requeridos deben tener valor")
        
        if contact_method not in ['email', 'whatsapp']:
            raise ValueError(f"Método de contacto inválido: {contact_method}")
        
        # Crear registro de contacto
        contact = ContactOption(
            name=name,
            email=email,
            contact_method=contact_method,
            subject=subject,
            message=message
        )
        contact.save()
        
        # Procesar según el método
        if contact_method == 'email':
            ContactService.send_email_notification(contact)
        elif contact_method == 'whatsapp':
            ContactService.process_whatsapp_contact(contact)
        
        return contact
    
    @staticmethod
    def send_email_notification(contact: ContactOption) -> bool:
        """
        Envía notificación por email al equipo de contacto.
        
        Args:
            contact: Instancia de ContactOption
            
        Returns:
            bool: True si fue enviado exitosamente, False si hubo error
        """
        try:
            email_body = ContactService._format_email_body(contact)
            
            email = EmailMessage(
                subject=f"Nuevo contacto: {contact.subject}",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.CONTACT_EMAIL]
            )
            
            email.send(fail_silently=False)
            logger.info(f"Email de contacto enviado desde {contact.email} referente a '{contact.subject}'")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de contacto para {contact.id}: {e}")
            return False
    
    @staticmethod
    def process_whatsapp_contact(contact: ContactOption) -> None:
        """
        Procesa un contacto iniciado por WhatsApp.
        
        Actualmente solo registra el evento. Puede extenderse para:
        - Integrar con API de WhatsApp
        - Enviar notificación al equipo
        
        Args:
            contact: Instancia de ContactOption
        """
        logger.info(f"Contacto por WhatsApp registrado desde {contact.email}: {contact.subject}")
    
    @staticmethod
    def _format_email_body(contact: ContactOption) -> str:
        """Formatea el cuerpo del email de notificación"""
        return f"""
Nuevo mensaje de contacto:

Nombre: {contact.name}
Email: {contact.email}
Asunto: {contact.subject}
Fecha: {contact.created_at.strftime('%d/%m/%Y %H:%M')}

--- Mensaje ---
{contact.message}

---
Responder directamente a: {contact.email}
"""

"""
Contact App Services

Contiene la lógica de negocio pura para manejo de contactos.
"""
import logging
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction

from .models import ContactOption

logger = logging.getLogger(__name__)


class ContactRateLimited(Exception):
    """Excepción lanzada cuando una IP o cliente excede el límite de contactos."""
    def __init__(self, ip: str, max_allowed: int = 5):
        self.ip = ip
        self.max_allowed = max_allowed
        super().__init__(f"Rate limit excedido para IP: {ip} (máximo {max_allowed}/hora)")


class ContactService:
    """Servicio para manejo de contactos y notificaciones"""

    MAX_SUBMISSIONS_PER_HOUR = 5

    @staticmethod
    def check_rate_limit(client_ip: str) -> None:
        """
        Verifica si una IP ha excedido el límite de envíos por hora usando Django Cache.

        Args:
            client_ip: Dirección IP del cliente.

        Raises:
            ContactRateLimited: Si la IP superó MAX_SUBMISSIONS_PER_HOUR en la última hora.
        """
        if not client_ip:
            return

        key = f"contact:rate_limit:{client_ip}"
        cache.add(key, 0, timeout=3600)
        count = cache.incr(key)
        if count > ContactService.MAX_SUBMISSIONS_PER_HOUR:
            logger.warning("Rate limit excedido para contacto (ip=%s, intentos=%s)", client_ip, count)
            raise ContactRateLimited(client_ip, ContactService.MAX_SUBMISSIONS_PER_HOUR)

    @staticmethod
    def create_contact(name: str, email: str, contact_method: str, subject: str, message: str) -> ContactOption:
        """
        Crea un nuevo registro de contacto y encola la notificación asíncrona vía Celery.

        Args:
            name: Nombre del contactante
            email: Email del contactante
            contact_method: Método de contacto ('email' o 'whatsapp')
            subject: Asunto del mensaje
            message: Cuerpo del mensaje

        Returns:
            ContactOption: Instancia guardada del contacto

        Raises:
            ValueError: Si los parámetros o validaciones del modelo fallan
        """
        # Validar campos obligatorios
        if not all([name, email, subject, message]):
            raise ValueError("Todos los campos requeridos deben tener valor")

        if contact_method not in ['email', 'whatsapp']:
            raise ValueError(f"Método de contacto inválido: {contact_method}")

        # Construir y validar modelo contra sus validadores (anti-CRLF, longitud, email)
        contact = ContactOption(
            name=name.strip(),
            email=email.strip(),
            contact_method=contact_method,
            subject=subject.strip(),
            message=message.strip()
        )
        try:
            contact.full_clean()
        except ValidationError as exc:
            raise ValueError("; ".join(exc.messages)) from exc

        contact.save()

        # Encolar notificación asíncrona unificada vía Celery
        from contact.tasks import send_contact_notification_task
        transaction.on_commit(lambda: send_contact_notification_task.delay(contact.id))

        return contact

    @staticmethod
    def send_email_notification(contact: ContactOption) -> bool:
        """
        Envía notificación por email al equipo de contacto de Bulonera Alvear.

        Args:
            contact: Instancia de ContactOption

        Returns:
            bool: True si fue enviado exitosamente, False si hubo error
        """
        try:
            email_body = ContactService._format_email_body(contact)

            email = EmailMessage(
                subject=f"Nuevo contacto [{contact.get_contact_method_display()}]: {contact.subject}",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.CONTACT_EMAIL],
                reply_to=[contact.email],
            )

            email.send(fail_silently=False)
            logger.info("Email de notificación de contacto enviado exitosamente (contact_id=%s)", contact.id)
            return True

        except Exception:
            logger.error("Error enviando email de contacto (contact_id=%s)", contact.id, exc_info=True)
            return False

    @staticmethod
    def _format_email_body(contact: ContactOption) -> str:
        """Formatea el cuerpo del email de notificación"""
        return f"""Nuevo mensaje de contacto en Bulonera Alvear:

Nombre: {contact.name}
Email: {contact.email}
Canal preferido de respuesta: {contact.get_contact_method_display()}
Asunto: {contact.subject}
Fecha: {contact.created_at.strftime('%d/%m/%Y %H:%M')}

--- Mensaje ---
{contact.message}

---
Responder directamente a este correo o al email: {contact.email}
"""

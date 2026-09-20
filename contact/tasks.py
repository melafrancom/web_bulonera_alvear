"""Celery tasks for contact app."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_contact_notification_task(self, contact_id: int) -> dict:
    """
    Envía notificación por email de forma asíncrona cuando se registra un contacto.

    Args:
        contact_id: ID del ContactOption a notificar.

    Raises:
        self.retry: Si el envío falla, reintenta con backoff exponencial.
    """
    from contact.models import ContactOption
    from contact.services import ContactService

    try:
        contact = ContactOption.objects.get(pk=contact_id)
        sent = ContactService.send_email_notification(contact)
        if not sent:
            raise RuntimeError(f"Fallo en envío de email para contact_id={contact_id}")
        return {'status': 'success', 'contact_id': contact_id}
    except ContactOption.DoesNotExist:
        logger.error("ContactOption con id=%s no encontrado, descartando tarea", contact_id)
        return {'status': 'error', 'message': 'Contact not found'}
    except Exception as exc:
        logger.warning(
            "Reintentando notificación de contacto (id=%s, intento=%s): %s",
            contact_id, self.request.retries, exc
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

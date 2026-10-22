"""Celery tasks for orders app."""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_revocation_notification_task(self, revocation_id: int) -> dict:
    """
    Envía únicamente una alerta interna al equipo comercial.
    No responde automáticamente al consumidor (la atención es humana).
    """
    from orders.models import OrderRevocation

    try:
        revocation = OrderRevocation.objects.get(pk=revocation_id)

        subject_team = f"[ARREPENTIMIENTO] Solicitud {revocation.revocation_code} — {revocation.customer_name}"
        message_team = (
            f"Nueva solicitud de revocación recibida ({revocation.get_origin_display()}):\n\n"
            f"- Código asignado: {revocation.revocation_code}\n"
            f"- Cliente: {revocation.customer_name}\n"
            f"- Medio de contacto ({revocation.get_contact_method_display()}): {revocation.contact_value}\n"
            f"- Referencia informada: {revocation.order_reference or 'No informada'}\n"
            f"- Comentarios: {revocation.details or 'Sin comentarios adicionales'}\n"
            f"- Fecha: {revocation.created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"REGLA LEGAL (Disp. 954/2025): Se deben adoptar medidas para efectivizar la "
            f"revocación dentro de las 24 horas corridas. En solicitudes recibidas por WhatsApp, "
            f"recuerde enviar el código de acuse al chat del cliente."
        )
        staff_recipient = getattr(settings, 'CONTACT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        send_mail(
            subject=subject_team,
            message=message_team,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[staff_recipient],
            fail_silently=False
        )

        return {'status': 'success', 'revocation_id': revocation_id, 'code': revocation.revocation_code}

    except OrderRevocation.DoesNotExist:
        logger.error("OrderRevocation id=%s no encontrada, descartando tarea", revocation_id)
        return {'status': 'error', 'message': 'Not found'}
    except Exception as exc:
        logger.warning(
            "Reintentando notificación de arrepentimiento (id=%s, intento=%s): %s",
            revocation_id, self.request.retries, exc
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

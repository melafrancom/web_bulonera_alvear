"""
Tests para tareas asíncronas de Orders (Celery).
"""
import pytest
from unittest.mock import patch
from django.core import mail
from orders.models import OrderRevocation
from orders.tasks import send_revocation_notification_task


@pytest.mark.django_db
class TestRevocationNotificationTask:
    """Tests para send_revocation_notification_task."""

    def test_task_sends_internal_alert_to_staff_only(self):
        """La tarea envía notificación únicamente al equipo comercial, nunca al cliente."""
        revocation = OrderRevocation.objects.create(
            revocation_code="ARR-20261022-TEST001",
            customer_name="Empresa Constructora SA",
            contact_method="whatsapp",
            contact_value="3624001122",
            order_reference="ORD-9988",
            details="Solicito revocación por compra duplicada"
        )

        result = send_revocation_notification_task(revocation.id)

        assert result['status'] == 'success'
        assert result['code'] == 'ARR-20261022-TEST001'
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert "[ARREPENTIMIENTO]" in sent_email.subject
        assert "ARR-20261022-TEST001" in sent_email.body
        assert "Empresa Constructora SA" in sent_email.body
        # El destinatario no es el cliente, sino el email del staff
        assert "3624001122" not in sent_email.to

    def test_task_nonexistent_revocation_returns_error(self):
        """Si la revocación no existe, la tarea descarta sin fallar con error no controlado."""
        result = send_revocation_notification_task(999999)
        assert result['status'] == 'error'
        assert len(mail.outbox) == 0

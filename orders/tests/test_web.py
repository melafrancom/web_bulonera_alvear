"""
Tests de seguridad de vistas web de Orders.
"""
import pytest
from django.urls import reverse
from orders.models import Order
from account.models import Account


@pytest.mark.django_db
class TestOrderCompleteIDOR:
    """AUD-201: order_complete debe requerir login y scoping de usuario."""

    def test_anonymous_redirects_to_login(self, client):
        """Acceso anónimo a order_complete redirige a login."""
        url = reverse('orders:order_complete', args=['20240101001'])
        response = client.get(url)
        assert response.status_code == 302
        assert 'login' in response.url

    def test_user_cannot_see_other_user_order(self, client_with_user, user):
        """Usuario autenticado NO puede ver órdenes de otro usuario."""
        other_user = Account.objects.create_user(
            first_name='Other', last_name='User',
            username='other@test.com', email='other@test.com',
            password='testpass123'
        )
        order = Order.objects.create(
            user=other_user,
            first_name='Other', last_name='User',
            phone='123', email='other@test.com',
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101099'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 404

    def test_user_can_see_own_order(self, client_with_user, user):
        """Usuario autenticado puede ver su propia orden."""
        order = Order.objects.create(
            user=user,
            first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101001'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestPaymentsView:
    """AUD-203: Vista payments solo acepta POST."""

    def test_payments_rejects_get(self, client_with_user):
        """GET a payments debe retornar 405."""
        url = reverse('orders:payments')
        response = client_with_user.get(url)
        assert response.status_code == 405

    def test_payments_unauthenticated_redirects(self, client):
        """Acceso sin login redirige."""
        url = reverse('orders:payments')
        response = client.post(url, content_type='application/json')
        assert response.status_code == 302
        assert 'login' in response.url


@pytest.mark.django_db
class TestOrderCompleteNoindex:
    """SEO: order_complete incluye noindex."""

    def test_template_has_noindex(self, client_with_user, user):
        """El template incluye meta robots noindex."""
        order = Order.objects.create(
            user=user,
            first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101001'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 200
        assert b'noindex' in response.content

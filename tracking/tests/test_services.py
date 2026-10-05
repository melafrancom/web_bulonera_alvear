"""
Tests unitarios y de integración para la capa de servicios de tracking (ConsentService, TrackingPayloadService, MetaCapiService).

QUÉ:
    Valida la extracción de consentimiento por cookies, la sanitización/hasheo
    de identificadores PII, la construcción de payloads normalizados (ADR-01 y ADR-04)
    y el encolamiento asíncrono idempotente hacia Meta CAPI.
POR QUÉ:
    Garantizar la protección de datos personales (GDPR/ePrivacy), la consistencia
    de tipos de datos hacia Meta/GA4 (evitando errores por coma decimal en ARS) y
    la prevención de conversiones duplicadas en el backend.
CÓMO:
    Aplica bloques Arrange-Act-Assert (AAA), mocks controlados de Celery/Cache
    y fixtures de base de datos para pedidos y productos.
"""
import hashlib
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.test import RequestFactory
from django.core.cache import cache

from orders.models import Order, OrderProduct
from tracking.services import (
    ConsentService,
    TrackingPayloadService,
    MetaCapiService,
)


@pytest.fixture
def rf():
    """Generador de peticiones HTTP simuladas."""
    return RequestFactory()


@pytest.fixture
def mock_order(db, user, product):
    """
    Crea una orden de prueba completa con ítems para tests de payload.
    """
    order = Order.objects.create(
        user=user,
        first_name='Juan',
        last_name='Perez',
        phone='+54 9 11 2345-6789',
        email='juan.perez@example.com',
        address_line_1='Av. Alvear 1234',
        country='AR',
        city='Buenos Aires',
        state='CABA',
        order_number='20261004001',
        order_total=Decimal('15750.50'),
        status='New',
        is_ordered=True,
    )
    OrderProduct.objects.create(
        order=order,
        user=user,
        product=product,
        quantity=3,
        purchase_price=Decimal('5250.16'),
        ordered=True,
    )
    return order


# ============================================================================
# 1. Tests para ConsentService
# ============================================================================

class TestConsentService:
    """Suite de pruebas para ConsentService verificando lectura de la cookie ba_consent."""

    def test_has_advertising_consent_returns_true_when_d_flag_is_one(self, rf):
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=1'

        # Act
        has_consent = ConsentService.has_advertising_consent(request)

        # Assert
        assert has_consent is True

    def test_has_advertising_consent_returns_false_when_d_flag_is_zero(self, rf):
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=0'

        # Act
        has_consent = ConsentService.has_advertising_consent(request)

        # Assert
        assert has_consent is False

    def test_has_advertising_consent_returns_false_when_cookie_is_missing_or_empty(self, rf):
        # Arrange
        request = rf.get('/')

        # Act & Assert
        assert ConsentService.has_advertising_consent(request) is False

        # Arrange con cookie vacía o formato malicioso
        request.COOKIES['ba_consent'] = 'malformed_value'
        assert ConsentService.has_advertising_consent(request) is False

    def test_has_analytics_consent_returns_true_when_a_flag_is_one(self, rf):
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=0'

        # Act
        has_consent = ConsentService.has_analytics_consent(request)

        # Assert
        assert has_consent is True

    def test_has_analytics_consent_returns_false_when_a_flag_is_zero(self, rf):
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=0|d=1'

        # Act
        has_consent = ConsentService.has_analytics_consent(request)

        # Assert
        assert has_consent is False


# ============================================================================
# 2. Tests para TrackingPayloadService
# ============================================================================

class TestTrackingPayloadService:
    """Suite de pruebas para normalización y sanitización de datos de tracking."""

    def test_hash_value_trims_lowercases_and_computes_sha256(self):
        # Arrange
        raw_email = "  Juan.Perez@Example.COM  "
        expected_hash = hashlib.sha256(b"juan.perez@example.com").hexdigest()

        # Act
        result = TrackingPayloadService.hash_value(raw_email)

        # Assert
        assert result == expected_hash

    def test_hash_value_returns_empty_string_for_falsy_input(self):
        # Arrange & Act & Assert
        assert TrackingPayloadService.hash_value("") == ""
        assert TrackingPayloadService.hash_value(None) == ""

    def test_extract_user_data_filters_empty_values_and_extracts_cookies(self, rf):
        # Arrange
        request = rf.get('/', HTTP_USER_AGENT='Mozilla/5.0 TestBrowser', REMOTE_ADDR='190.180.10.5')
        request.COOKIES['_fbp'] = 'fb.1.123456789.987654321'
        # _fbc no configurada intencionalmente

        # Act
        user_data = TrackingPayloadService.extract_user_data(request)

        # Assert
        assert user_data['client_user_agent'] == 'Mozilla/5.0 TestBrowser'
        assert user_data['fbp'] == 'fb.1.123456789.987654321'
        assert 'fbc' not in user_data  # Debe haber sido filtrado por estar vacío
        assert 'client_ip_address' in user_data

    @pytest.mark.django_db
    def test_build_purchase_custom_data_conforms_to_adr01_product_code_and_floats(self, mock_order):
        # Arrange & Act
        custom_data = TrackingPayloadService.build_purchase_custom_data(mock_order)

        # Assert
        assert custom_data['currency'] == 'ARS'
        assert custom_data['value'] == 15750.50
        assert isinstance(custom_data['value'], float)
        assert custom_data['content_type'] == 'product'
        assert len(custom_data['contents']) == 1

        first_item = custom_data['contents'][0]
        # REGLA ADR-01: El ID debe ser estrictamente product.code, no el slug ni el id autoincremental
        assert first_item['id'] == 'SCREW-001'
        assert first_item['quantity'] == 3
        assert first_item['item_price'] == 5250.16
        assert isinstance(first_item['item_price'], float)

    @pytest.mark.django_db
    def test_extract_user_data_includes_hashed_pii_for_authenticated_user(self, rf, user):
        """
        QUÉ:
            Verifica que si la petición proviene de un usuario autenticado con email y teléfono,
            se extraigan y hasheen en sha256 para maximizar el Event Match Quality (EMQ).
        POR QUÉ:
            Meta CAPI exige hasheo previo en SHA-256 sin espacios y en minúsculas para em y ph.
        """
        # Arrange
        user.email = "usuario.test@example.com"
        user.phone_number = "+54 9 362 412-3456"
        user.save()

        request = rf.get('/', HTTP_USER_AGENT='Mozilla/5.0 TestBrowser')
        request.user = user

        # Act
        user_data = TrackingPayloadService.extract_user_data(request)

        # Assert
        expected_em = hashlib.sha256(b"usuario.test@example.com").hexdigest()
        expected_ph = hashlib.sha256(b"5493624123456").hexdigest()
        assert user_data['em'] == expected_em
        assert user_data['ph'] == expected_ph

    @pytest.mark.django_db
    def test_build_addtocart_custom_data_conforms_to_adr01(self, product):
        """
        QUÉ:
            Verifica que el custom_data de AddToCart use product.code y cálculo de total en float.
        POR QUÉ:
            Consistencia de IDs con el catálogo de Meta y tipos nativos float en el JSON de CAPI.
        """
        # Arrange
        quantity = 4

        # Act
        custom_data = TrackingPayloadService.build_addtocart_custom_data(product, quantity)

        # Assert
        assert custom_data['currency'] == 'ARS'
        expected_val = float(product.price * quantity)
        assert custom_data['value'] == expected_val
        assert isinstance(custom_data['value'], float)
        assert custom_data['content_type'] == 'product'
        assert len(custom_data['contents']) == 1
        assert custom_data['contents'][0]['id'] == str(product.code)
        assert custom_data['contents'][0]['quantity'] == 4
        assert custom_data['contents'][0]['item_price'] == float(product.price)



# ============================================================================
# 3. Tests para MetaCapiService
# ============================================================================

@pytest.mark.django_db
class TestMetaCapiService:
    """Suite de pruebas para encolamiento asíncrono y control de idempotencia de Meta CAPI."""

    def test_enqueue_purchase_aborts_and_returns_false_without_advertising_consent(self, rf, mock_order):
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=0'  # Consentimiento publicitario rechazado

        # Act
        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            result = MetaCapiService.enqueue_purchase(mock_order, request)

            # Assert
            assert result is False
            mock_delay.assert_not_called()

    def test_enqueue_purchase_success_enqueues_celery_task_with_expected_payload(self, rf, mock_order):
        # Arrange
        cache.clear()
        request = rf.get('/', HTTP_USER_AGENT='TestAgent')
        request.COOKIES['ba_consent'] = 'a=1|d=1'  # Consentimiento aceptado

        # Act
        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            result = MetaCapiService.enqueue_purchase(mock_order, request)

            # Assert
            assert result is True
            mock_delay.assert_called_once()
            call_args = mock_delay.call_args[0]
            event_name, event_id, user_data, custom_data = call_args

            assert event_name == 'Purchase'
            assert event_id == f"purchase.{mock_order.order_number}"
            # Hasheo de PII esperado
            assert user_data['em'] == hashlib.sha256(b'juan.perez@example.com').hexdigest()
            assert user_data['ph'] == hashlib.sha256(b'5491123456789').hexdigest()
            # Custom data
            assert custom_data['value'] == 15750.50
            assert custom_data['contents'][0]['id'] == 'SCREW-001'

    def test_enqueue_purchase_enforces_idempotency_preventing_duplicate_events(self, rf, mock_order):
        # Arrange
        cache.clear()
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=1'

        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            # Act - Primer envío
            first_attempt = MetaCapiService.enqueue_purchase(mock_order, request)

            # Act - Segundo envío idéntico (simula recarga o doble hook)
            second_attempt = MetaCapiService.enqueue_purchase(mock_order, request)

            # Assert
            assert first_attempt is True
            assert second_attempt is False
            assert mock_delay.call_count == 1  # Solo se encoló una vez

    def test_enqueue_add_to_cart_aborts_without_advertising_consent(self, rf, product):
        """
        QUÉ:
            Valida que AddToCart no se envíe a Meta si falta el consentimiento publicitario.
        POR QUÉ:
            Cumplimiento normativo y respeto del banner de cookies.
        """
        # Arrange
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=0'

        # Act
        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            result = MetaCapiService.enqueue_add_to_cart(request, product, quantity=2, event_id='cart-uuid-123')

            # Assert
            assert result is False
            mock_delay.assert_not_called()

    def test_enqueue_add_to_cart_success_enqueues_celery_task(self, rf, product):
        """
        QUÉ:
            Valida el encolamiento exitoso de AddToCart con el event_id provisto por el cliente.
        POR QUÉ:
            Deduplicación hybrid Browser + Server vía event_id común.
        """
        # Arrange
        cache.clear()
        request = rf.get('/', HTTP_USER_AGENT='TestBrowser')
        request.COOKIES['ba_consent'] = 'a=1|d=1'
        event_id = 'test-addtocart-uuid-456'

        # Act
        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            result = MetaCapiService.enqueue_add_to_cart(request, product, quantity=3, event_id=event_id)

            # Assert
            assert result is True
            mock_delay.assert_called_once()
            call_args = mock_delay.call_args[0]
            event_name, queued_event_id, user_data, custom_data = call_args

            assert event_name == 'AddToCart'
            assert queued_event_id == event_id
            assert custom_data['contents'][0]['id'] == str(product.code)
            assert custom_data['contents'][0]['quantity'] == 3

    def test_enqueue_add_to_cart_enforces_idempotency(self, rf, product):
        """
        QUÉ:
            Valida que múltiples envíos con el mismo event_id sean ignorados por idempotencia en cache.
        POR QUÉ:
            Evitar registrar dos veces el mismo evento si el usuario reintenta la petición.
        """
        # Arrange
        cache.clear()
        request = rf.get('/')
        request.COOKIES['ba_consent'] = 'a=1|d=1'
        event_id = 'test-duplicate-uuid-789'

        with patch('tracking.services.send_meta_capi_event.delay') as mock_delay:
            # Act - Primer intento
            first_attempt = MetaCapiService.enqueue_add_to_cart(request, product, quantity=1, event_id=event_id)
            # Act - Segundo intento con el mismo event_id
            second_attempt = MetaCapiService.enqueue_add_to_cart(request, product, quantity=1, event_id=event_id)

            # Assert
            assert first_attempt is True
            assert second_attempt is False
            assert mock_delay.call_count == 1


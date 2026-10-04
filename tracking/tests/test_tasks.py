"""
Tests unitarios para tareas asíncronas de Celery en tracking (send_meta_capi_event).

QUÉ:
    Valida la ejecución asíncrona de envío de eventos hacia Meta Conversions API (Graph API v19.0).
POR QUÉ:
    Verificar que el worker maneje correctamente credenciales faltantes, respuestas exitosas,
    errores transitorios 5xx (reintentos exponenciales) y errores no recuperables 4xx.
CÓMO:
    Mocks de requests.post, override de settings de Django y verificación de llamadas retry en Celery.
"""
from unittest.mock import patch, MagicMock
import pytest
import requests
from celery.exceptions import Retry
from django.test import override_settings

from tracking.tasks import send_meta_capi_event


class TestSendMetaCapiEventTask:
    """Suite de pruebas para la tarea Celery send_meta_capi_event."""

    @override_settings(META_PIXEL_ID=None, META_CAPI_TOKEN=None)
    def test_send_meta_capi_aborts_when_credentials_are_missing(self):
        # Arrange & Act
        with patch('requests.post') as mock_post:
            result = send_meta_capi_event('Purchase', 'purchase.1001', {}, {})

            # Assert
            assert result is False
            mock_post.assert_not_called()

    @override_settings(META_PIXEL_ID='406099791293899', META_CAPI_TOKEN='test_token_123')
    def test_send_meta_capi_success_posts_payload_to_graph_api(self):
        # Arrange
        user_data = {'em': 'hashed_email'}
        custom_data = {'value': 1200.0, 'currency': 'ARS'}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'events_received': 1, 'fbtrace_id': 'xyz123'}

        # Act
        with patch('requests.post', return_value=mock_response) as mock_post:
            result = send_meta_capi_event('Purchase', 'purchase.1001', user_data, custom_data)

            # Assert
            assert result == {'events_received': 1, 'fbtrace_id': 'xyz123'}
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == 'https://graph.facebook.com/v19.0/406099791293899/events'
            sent_payload = kwargs['json']
            assert sent_payload['access_token'] == 'test_token_123'
            data_item = sent_payload['data'][0]
            assert data_item['event_name'] == 'Purchase'
            assert data_item['event_id'] == 'purchase.1001'
            assert data_item['action_source'] == 'website'
            assert data_item['user_data'] == user_data
            assert data_item['custom_data'] == custom_data

    @override_settings(META_PIXEL_ID='406099791293899', META_CAPI_TOKEN='test_token_123')
    def test_send_meta_capi_retries_on_5xx_server_error(self):
        # Arrange
        mock_err_response = MagicMock()
        mock_err_response.status_code = 502
        http_error = requests.exceptions.HTTPError("Bad Gateway", response=mock_err_response)

        # Act & Assert
        with patch('requests.post', side_effect=http_error):
            # Simulamos el objeto bound task
            with patch.object(send_meta_capi_event, 'retry', side_effect=Retry) as mock_retry:
                with pytest.raises(Retry):
                    send_meta_capi_event('Purchase', 'purchase.1001', {}, {})

                mock_retry.assert_called_once()
                retry_kwargs = mock_retry.call_args[1]
                assert retry_kwargs['countdown'] == 60

    @override_settings(META_PIXEL_ID='406099791293899', META_CAPI_TOKEN='test_token_123')
    def test_send_meta_capi_does_not_retry_on_4xx_client_error(self):
        # Arrange
        mock_err_response = MagicMock()
        mock_err_response.status_code = 400
        http_error = requests.exceptions.HTTPError("Bad Request - Invalid Param", response=mock_err_response)

        # Act & Assert
        with patch('requests.post', side_effect=http_error):
            with patch.object(send_meta_capi_event, 'retry') as mock_retry:
                result = send_meta_capi_event('Purchase', 'purchase.1001', {}, {})

                # Errores 4xx son definitivos; no deben saturar la cola de reintentos
                assert result is False
                mock_retry.assert_not_called()

"""
Tests de seguridad para web_bulonera.
Cubren: SEC-001, SEC-003, SEC-006, SEC-009, SEC-011.
"""
import logging
import pytest
from django.test import Client, RequestFactory
from django.core.cache import cache


@pytest.mark.django_db
class TestCKEditorUploadProtection:
    """SEC-001: CKEditor upload/browse requiere staff autenticado."""

    def test_anonymous_upload_rejected(self, client: Client):
        """Visitante anónimo NO puede subir archivos."""
        response = client.post(
            '/ckeditor/upload/?CKEditorFuncNum=1',
            {'upload': ('test.png', b'\x89PNG\r\n\x1a\n', 'image/png')},
        )
        assert response.status_code in (302, 403)

    def test_anonymous_browse_rejected(self, client: Client):
        """Visitante anónimo NO puede explorar archivos."""
        response = client.get('/ckeditor/browse/')
        assert response.status_code in (302, 403)

    def test_non_staff_user_rejected(self, client: Client, user):
        """Usuario autenticado SIN staff NO puede subir."""
        client.force_login(user)
        response = client.post(
            '/ckeditor/upload/?CKEditorFuncNum=1',
            {'upload': ('test.png', b'\x89PNG\r\n\x1a\n', 'image/png')},
        )
        assert response.status_code in (302, 403)


class TestErrorLoggingMiddleware:
    """SEC-003: Excepciones deben loguearse al logger 'django', no al root."""

    def test_exception_uses_django_logger(self, caplog):
        from web_bulonera.middleware import ErrorLoggingMiddleware

        middleware = ErrorLoggingMiddleware(get_response=lambda r: None)
        request = RequestFactory().get('/test-path/')

        with caplog.at_level(logging.ERROR, logger='django'):
            middleware.process_exception(request, RuntimeError("boom"))

        assert any("Unhandled exception" in r.message for r in caplog.records)
        assert all(r.name == 'django' for r in caplog.records
                   if "Unhandled exception" in r.message)


class TestContextProcessorRobustness:
    """SEC-006: meta_settings resiliente ante cache corrupta."""

    def test_corrupted_cache_string(self):
        from web_bulonera.context_processors import meta_settings
        request = RequestFactory().get('/')
        cache.set('google_places_reviews_data', 'NOT_A_DICT', timeout=30)
        result = meta_settings(request)
        assert result['GOOGLE_BUSINESS_RATING'] is None
        assert result['GOOGLE_BUSINESS_REVIEWS_COUNT'] is None
        cache.delete('google_places_reviews_data')

    def test_corrupted_cache_list(self):
        from web_bulonera.context_processors import meta_settings
        request = RequestFactory().get('/')
        cache.set('google_places_reviews_data', [1, 2, 3], timeout=30)
        result = meta_settings(request)
        assert result['GOOGLE_BUSINESS_RATING'] is None
        cache.delete('google_places_reviews_data')

    def test_empty_cache_returns_none(self):
        from web_bulonera.context_processors import meta_settings
        request = RequestFactory().get('/')
        cache.delete('google_places_reviews_data')
        result = meta_settings(request)
        assert result['GOOGLE_BUSINESS_RATING'] is None

    def test_valid_cache_returns_values(self):
        from web_bulonera.context_processors import meta_settings
        request = RequestFactory().get('/')
        cache.set('google_places_reviews_data', {
            'rating': 4.8, 'total': 125
        }, timeout=30)
        result = meta_settings(request)
        assert result['GOOGLE_BUSINESS_RATING'] == 4.8
        assert result['GOOGLE_BUSINESS_REVIEWS_COUNT'] == 125
        cache.delete('google_places_reviews_data')


@pytest.mark.django_db
class TestSiteThemeSingleton:
    """SEC-009: El singleton debe loguear si se intenta crear duplicado."""

    def test_second_instance_blocked_with_warning(self, caplog):
        from web_bulonera.models import SiteTheme

        SiteTheme.objects.create(name="Original")

        with caplog.at_level(logging.WARNING, logger='django'):
            second = SiteTheme(name="Duplicado")
            second.save()

        assert SiteTheme.objects.count() == 1
        assert any("Intento bloqueado" in r.message for r in caplog.records)


@pytest.mark.django_db
class TestAPISchemaPermissions:
    """SEC-011: OpenAPI Schema y Swagger UI requieren usuario staff/admin."""

    def test_anonymous_cannot_access_schema(self, client: Client):
        response = client.get('/api/schema/')
        assert response.status_code in (401, 403)

    def test_anonymous_cannot_access_swagger_ui(self, client: Client):
        response = client.get('/api/docs/')
        assert response.status_code in (401, 403)

    def test_non_staff_user_cannot_access_schema(self, client: Client, user):
        client.force_login(user)
        response = client.get('/api/schema/')
        assert response.status_code in (401, 403)

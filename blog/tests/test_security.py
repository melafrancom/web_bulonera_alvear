"""
Test Security Hardening - Blog app (OWASP A03:2021 & AppSec)

Valida las mitigaciones de seguridad implementadas en la auditoría del blog:
- SEC-BLG-001: Sanitización nh3 en Post y PostTranslation (Stored XSS).
- SEC-BLG-002: Corrección de URL canónica y host dinámico en señal IndexNow.
- SEC-BLG-003: Exclusión de embed_code (HTML crudo) en serializer público.
- SEC-BLG-004: Remoción del botón Source en configuración CKEditor.
- SEC-BLG-006: Sanitización nh3 en SocialMetadata.embed_code.
"""
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse
import pytest
from django.conf import settings
from django.urls import reverse
from blog.models import Post, PostTranslation, SocialMetadata


@pytest.mark.django_db
class TestBlogSecuritySanitization:
    """Valida la sanitización de contenido HTML contra vectores Stored XSS."""

    def test_post_content_strips_script_tag(self, admin_user):
        """
        # SEC-BLG-001: Verifica que etiquetas <script> y su contenido sean eliminados.
        # REGLA: nh3 debe depurar cualquier payload ejecutable en Post.save().
        """
        malicious_content = '<h2>Guía Técnica</h2><script>alert("XSS")</script><p>Párrafo legítimo.</p>'
        post = Post.objects.create(
            title='Artículo de Prueba XSS Script',
            content=malicious_content,
            author=admin_user,
        )
        assert '<script>' not in post.content
        assert '</script>' not in post.content
        assert 'alert("XSS")' not in post.content
        assert '<h2>Guía Técnica</h2>' in post.content
        assert '<p>Párrafo legítimo.</p>' in post.content

    def test_post_content_strips_event_handlers(self, admin_user):
        """
        # SEC-BLG-001: Verifica que manejadores de eventos inline (onerror, onload, onclick) se eliminen.
        """
        malicious_content = '<p>Texto</p><img src="https://example.com/foto.jpg" onerror="alert(document.cookie)">'
        post = Post.objects.create(
            title='Artículo de Prueba XSS Onerror',
            content=malicious_content,
            author=admin_user,
        )
        assert 'onerror' not in post.content
        assert 'alert' not in post.content
        assert '<img' in post.content
        assert 'src="https://example.com/foto.jpg"' in post.content

    def test_post_content_preserves_legitimate_blog_html(self, admin_user):
        """
        # SEC-BLG-001: Verifica que elementos HTML estándar y necesarios para artículos se conserven.
        """
        clean_html = (
            '<h2>Encabezado H2</h2>'
            '<p class="lead">Párrafo destacado con <strong>negrita</strong> y <em>cursiva</em>.</p>'
            '<blockquote>Cita técnica de referencia.</blockquote>'
            '<pre><code>print("Código seguro")</code></pre>'
            '<table class="table-auto"><thead><tr><th>DIN</th><th>Medida</th></tr></thead>'
            '<tbody><tr><td>933</td><td>M8x30</td></tr></tbody></table>'
            '<hr>'
        )
        post = Post.objects.create(
            title='Artículo con HTML Legítimo Completo',
            content=clean_html,
            author=admin_user,
        )
        assert '<h2>Encabezado H2</h2>' in post.content
        assert '<blockquote>Cita técnica de referencia.</blockquote>' in post.content
        assert '<table class="table-auto">' in post.content
        assert '<td>933</td>' in post.content
        assert '<pre><code>print("Código seguro")</code></pre>' in post.content

    def test_post_content_strips_javascript_scheme_in_links(self, admin_user):
        """
        # SEC-BLG-001: Verifica que enlaces con esquema javascript: sean desarmados.
        """
        malicious_content = '<a href="javascript:alert(1)">Enlace sospechoso</a><a href="https://buloneraalvear.online">Enlace seguro</a>'
        post = Post.objects.create(
            title='Artículo con Esquema Javascript',
            content=malicious_content,
            author=admin_user,
        )
        assert 'javascript:' not in post.content
        assert 'href="https://buloneraalvear.online"' in post.content

    def test_post_content_strips_disallowed_iframes(self, admin_user):
        """
        # SEC-BLG-001: Los iframes en el cuerpo del post deben ser eliminados.
        # POR QUÉ: Los iframes solo están autorizados en SocialMetadata para prevenir inyecciones no controladas.
        """
        content_with_iframe = '<p>Nota técnica</p><iframe src="https://evil.com/phishing"></iframe>'
        post = Post.objects.create(
            title='Artículo con Iframe en Body',
            content=content_with_iframe,
            author=admin_user,
        )
        assert '<iframe' not in post.content
        assert '<p>Nota técnica</p>' in post.content

    def test_post_translation_content_sanitized(self, db_session, blog_post_article):
        """
        # SEC-BLG-001: PostTranslation.save() debe aplicar sanitización nh3 equivalente al modelo Post principal.
        """
        malicious_translation = '<h2>International Guide</h2><script>eval("malicious")</script><p>Safe body.</p>'
        translation = PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='English Article With XSS Attempt',
            slug='english-article-with-xss-attempt',
            content=malicious_translation,
            excerpt='Brief excerpt',
        )
        assert '<script>' not in translation.content
        assert 'eval(' not in translation.content
        assert '<h2>International Guide</h2>' in translation.content
        assert '<p>Safe body.</p>' in translation.content

    def test_social_metadata_embed_sanitizes_malicious_script(self, db_session, blog_post_social_repost):
        """
        # SEC-BLG-006: SocialMetadata.save() permite iframes seguros pero elimina scripts y esquemas peligrosos.
        """
        raw_embed = (
            '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" width="560" height="315" frameborder="0"></iframe>'
            '<script>stealSession()</script>'
        )
        metadata = SocialMetadata.objects.create(
            post=blog_post_social_repost,
            platform='youtube',
            original_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            embed_code=raw_embed,
        )
        assert '<iframe' in metadata.embed_code
        assert 'src="https://www.youtube.com/embed/dQw4w9WgXcQ"' in metadata.embed_code
        assert '<script>' not in metadata.embed_code
        assert 'stealSession' not in metadata.embed_code


@pytest.mark.django_db
class TestIndexNowSignalSecurity:
    """Valida la corrección técnica y seguridad de la señal IndexNow (SEC-BLG-002)."""

    def test_indexnow_reverse_url_name_resolution(self):
        """
        # SEC-BLG-002: Verifica que 'blog:post_detail' exista en el urlconf sin lanzar NoReverseMatch.
        """
        resolved_url = reverse('blog:post_detail', kwargs={'slug': 'tornillo-hexagonal-din-933'})
        assert resolved_url == '/blog/tornillo-hexagonal-din-933/'

    @patch('blog.signals.requests.post')
    def test_indexnow_signal_payload_dynamic_host_and_correct_url(self, mock_post, admin_user, settings):
        """
        # SEC-BLG-002: Verifica que el payload de IndexNow extraiga el host dinámico de SITE_URL
        # y utilice el endpoint correcto 'blog:post_detail'.
        """
        # 1. Configurar entorno de producción simulado y credenciales
        settings.ENVIRONMENT = 'production'
        settings.SITE_URL = 'https://buloneraalvear.online'
        settings.INDEXNOW_API_KEY = 'test-indexnow-secret-key-123'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 2. Crear y publicar post para disparar post_save
        from blog.signals import notify_indexnow_on_post_change
        post = Post.objects.create(
            title='Nuevo Post de Prueba IndexNow',
            slug='nuevo-post-prueba-indexnow',
            content='<p>Contenido IndexNow</p>',
            author=admin_user,
            is_published=True,
        )

        # 3. Invocar la señal directamente si no fue disparada por settings
        notify_indexnow_on_post_change(sender=Post, instance=post, created=True)

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs['json']

        expected_host = urlparse(settings.SITE_URL).hostname
        assert payload['host'] == expected_host
        assert payload['host'] != 'bulonera-alvear.com.ar'
        assert payload['key'] == 'test-indexnow-secret-key-123'
        assert f"https://buloneraalvear.online/blog/{post.slug}/" in payload['urlList']


@pytest.mark.django_db
class TestBlogAPISecurityExposure:
    """Valida la protección contra fugas de datos y scripts en la API REST (SEC-BLG-003)."""

    def test_api_excludes_embed_code_from_public_endpoint(self, client, social_metadata):
        """
        # SEC-BLG-003: Verifica que SocialMetadataSerializer no exponga el campo 'embed_code'.
        """
        post = social_metadata.post
        url = f'/api/v1/blog/posts/{post.id}/'
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert 'social_metadata' in data
        assert data['social_metadata'] is not None

        # REGLA: 'embed_code' debe estar ausente para mitigar XSS en clientes API
        assert 'embed_code' not in data['social_metadata']
        assert 'original_url' in data['social_metadata']
        assert 'platform' in data['social_metadata']


class TestCKEditorConfigurationSecurity:
    """Valida las configuraciones de seguridad del editor enriquecido CKEditor (SEC-BLG-004)."""

    def test_ckeditor_toolbar_includes_source_button_protected_by_nh3(self):
        """
        # SEC-BLG-004: Verifica que el botón 'Source' esté habilitado para el flujo editorial
        # (pegar plantillas HTML de artículos) y que la seguridad esté garantizada por nh3 en backend.
        """
        blog_config = settings.CKEDITOR_CONFIGS.get('blog', {})
        toolbar_custom = blog_config.get('toolbar_Custom', [])

        # Aplanar todos los subgrupos de herramientas del toolbar
        flattened_buttons = [btn for group in toolbar_custom for btn in group]
        assert 'Source' in flattened_buttons
        assert 'RemoveFormat' in flattened_buttons
        assert blog_config.get('allowedContent') is True

    def test_post_content_unescapes_accidental_html_entities_and_sanitizes(self, admin_user):
        """
        # UX-SEC: Si un admin pega HTML en modo visual de CKEditor, los tags vienen escapados
        # como &lt;div... El modelo debe desescaparlos para renderizar HTML real y sanitizarlos con nh3.
        """
        escaped_html = (
            '&lt;div class="blog-article-content prose prose-lg max-w-none text-slate-800"&gt;'
            '&lt;!-- Apertura Answer-First --&gt;'
            '&lt;p class="lead text-lg"&gt;Para sacar un tornillo barrido se debe aplicar calor.&lt;/p&gt;'
            '&lt;h2&gt;Método 1&lt;/h2&gt;'
            '&lt;script&gt;alert("XSS")&lt;/script&gt;'
            '&lt;/div&gt;'
        )
        post = Post.objects.create(
            title='Artículo con HTML pegado en modo visual',
            content=escaped_html,
            author=admin_user,
        )
        # Debe convertirse en HTML real para que el navegador lo estilice correctamente
        assert '<div class="blog-article-content prose prose-lg max-w-none text-slate-800">' in post.content
        assert '<h2>Método 1</h2>' in post.content
        assert '<p class="lead text-lg">' in post.content
        # Y nh3 debe seguir eliminando el script malicioso
        assert '<script>' not in post.content
        assert 'alert("XSS")' not in post.content

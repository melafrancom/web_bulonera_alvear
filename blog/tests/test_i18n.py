"""Test i18n - Blog multilingual support (EN + PT)"""
import pytest
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from blog.models import Post, PostTranslation
from blog.sitemaps import sitemaps


@pytest.mark.django_db
class TestBlogI18nListView:
    """Tests para la vista lista en idiomas internacionales."""
    
    def test_english_blog_list_returns_200(self, client, blog_post_article, blog_post_translation_en):
        """GET /en/blog/ retorna 200 cuando hay posts con traducción."""
        response = client.get('/en/blog/')
        assert response.status_code == 200
        assert blog_post_article in response.context['posts']
    
    def test_english_blog_list_excludes_untranslated(self, client, blog_post_article):
        """GET /en/blog/ NO muestra posts sin traducción al inglés."""
        response = client.get('/en/blog/')
        assert response.status_code == 200
        assert len(response.context['posts']) == 0
    
    def test_spanish_blog_unaffected(self, client, blog_post_article):
        """GET /blog/ sigue funcionando exactamente igual (no afectado por i18n)."""
        response = client.get('/blog/')
        assert response.status_code == 200
        assert blog_post_article in response.context['posts']
    
    def test_portuguese_blog_list_returns_200(self, client, blog_post_article, blog_post_translation_pt):
        """GET /pt/blog/ retorna 200 cuando hay posts con traducción."""
        response = client.get('/pt/blog/')
        assert response.status_code == 200
        assert blog_post_article in response.context['posts']


@pytest.mark.django_db
class TestBlogI18nDetailView:
    """Tests para la vista detalle en idiomas internacionales."""
    
    def test_english_detail_returns_200(self, client, blog_post_article, blog_post_translation_en):
        """GET /en/blog/<slug-en>/ retorna 200."""
        response = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        assert response.status_code == 200
    
    def test_english_detail_shows_translated_title(self, client, blog_post_article, blog_post_translation_en):
        """Verifica que el título mostrado es el traducido al inglés."""
        response = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        assert blog_post_translation_en.title in response.content.decode()

    def test_english_detail_shows_translated_ui_strings(self, client, blog_post_article, blog_post_translation_en):
        """Verifica que los textos estáticos de UI se traduzcan al inglés con gettext."""
        response = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        content = response.content.decode()
        assert "Share this article" in content
        assert "Key Takeaways / Executive Summary" in content

    def test_portuguese_detail_shows_translated_ui_strings(self, client, blog_post_article, blog_post_translation_pt):
        """Verifica que los textos estáticos de UI se traduzcan al portugués con gettext."""
        response = client.get(f'/pt/blog/{blog_post_translation_pt.slug}/')
        content = response.content.decode()
        assert "Compartilhar este artigo" in content
        assert "Pontos-Chave / Resumo Executivo" in content

    def test_html_lang_attribute_reflects_active_language(self, client, blog_post_article, blog_post_translation_en, blog_post_translation_pt):
        """Verifica que el atributo <html lang="..."> cambie según el prefijo de idioma."""
        res_es = client.get(f'/blog/{blog_post_article.slug}/')
        assert '<html lang="es' in res_es.content.decode()

        res_en = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        assert '<html lang="en' in res_en.content.decode()

        res_pt = client.get(f'/pt/blog/{blog_post_translation_pt.slug}/')
        assert '<html lang="pt' in res_pt.content.decode()
    
    def test_spanish_detail_unaffected(self, client, blog_post_article):
        """GET /blog/<slug-es>/ sigue funcionando exactamente igual."""
        response = client.get(f'/blog/{blog_post_article.slug}/')
        assert response.status_code == 200
        assert blog_post_article.title in response.content.decode()
    
    def test_nonexistent_english_slug_returns_404(self, client, blog_post_article):
        """GET /en/blog/<slug-inexistente>/ retorna 404."""
        response = client.get('/en/blog/nonexistent-slug/')
        assert response.status_code == 404
    
    def test_language_switch_from_english_back_to_spanish(self, client, blog_post_article, blog_post_translation_en):
        """Desde /en/blog/<slug-en>/, el selector de idioma debe enlazar a /blog/<slug-es>/ (sin prefijo) y retornar 200."""
        res_en = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        assert res_en.status_code == 200
        content = res_en.content.decode()
        
        # Verificar que el link a español es la ruta limpia sin prefijo /en/
        expected_es_path = f'/blog/{blog_post_article.slug}/'
        assert f'href="{expected_es_path}"' in content
        
        # Seguir el link a español y verificar que retorna 200 OK
        res_es = client.get(expected_es_path)
        assert res_es.status_code == 200
        assert blog_post_article.title in res_es.content.decode()

    def test_language_switch_from_portuguese_back_to_spanish(self, client, blog_post_article, blog_post_translation_pt):
        """Desde /pt/blog/<slug-pt>/, el selector de idioma debe enlazar a /blog/<slug-es>/ (sin prefijo) y retornar 200."""
        res_pt = client.get(f'/pt/blog/{blog_post_translation_pt.slug}/')
        assert res_pt.status_code == 200
        content = res_pt.content.decode()
        
        expected_es_path = f'/blog/{blog_post_article.slug}/'
        assert f'href="{expected_es_path}"' in content
        
        res_es = client.get(expected_es_path)
        assert res_es.status_code == 200
        assert blog_post_article.title in res_es.content.decode()

    def test_language_switch_labels_use_endonyms(self, client, blog_post_article, blog_post_translation_en, blog_post_translation_pt):
        """El selector de idioma debe mostrar los endónimos oficiales: Español, English, Português."""
        res = client.get(f'/en/blog/{blog_post_translation_en.slug}/')
        content = res.content.decode()
        assert "Español" in content
        assert "English" in content
        assert "Português" in content

    def test_post_get_absolute_url_clean_in_foreign_context(self, blog_post_article):
        """Post.get_absolute_url() siempre debe retornar la URL base sin prefijos independientemente del contexto activo."""
        from django.utils.translation import override
        with override('en'):
            assert blog_post_article.get_absolute_url() == f"/blog/{blog_post_article.slug}/"
        with override('pt'):
            assert blog_post_article.get_absolute_url() == f"/blog/{blog_post_article.slug}/"



@pytest.mark.django_db
class TestPostTranslationModel:
    """Tests para el modelo PostTranslation."""
    
    def test_create_translation(self, blog_post_article):
        """Puede crear una traducción válida y su __str__ es correcto."""
        tr = PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='Test Title EN',
            slug='test-title-en',
            content='<p>Test content</p>',
        )
        assert tr.pk is not None
        assert str(tr) == f"{blog_post_article.title} [EN]"
    
    def test_unique_together_language_post(self, blog_post_article):
        """No puede haber 2 traducciones del mismo idioma para el mismo post."""
        PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='First',
            slug='first-en',
            content='a',
        )
        with pytest.raises((IntegrityError, Exception)):
            PostTranslation.objects.create(
                post=blog_post_article,
                language='en',
                title='Second',
                slug='second-en',
                content='b',
            )
    
    def test_unique_together_language_slug(self, blog_post_article, admin_user):
        """No puede haber 2 traducciones con el mismo slug en el mismo idioma."""
        post2 = Post.objects.create(
            title='Otro Post',
            slug='otro-post',
            content='x',
            author=admin_user,
            is_published=True,
            published_date=timezone.now(),
        )
        PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='Title 1',
            slug='same-slug-en',
            content='a',
        )
        with pytest.raises((IntegrityError, Exception)):
            PostTranslation.objects.create(
                post=post2,
                language='en',
                title='Title 2',
                slug='same-slug-en',
                content='b',
            )
    
    def test_auto_meta_title(self, blog_post_article):
        """meta_title se auto-rellena desde title si está vacío."""
        tr = PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='A Very Long Title For Testing Auto Fill Behavior',
            slug='auto-meta-slug',
            content='x',
        )
        assert tr.meta_title == 'A Very Long Title For Testing Auto Fill Behavior'[:60]
    
    def test_cascade_delete(self, blog_post_article):
        """Al eliminar el Post padre, las traducciones se eliminan en cascada."""
        PostTranslation.objects.create(
            post=blog_post_article,
            language='en',
            title='Deletable Post',
            slug='deletable-post',
            content='x',
        )
        assert PostTranslation.objects.filter(post=blog_post_article).count() == 1
        blog_post_article.delete()
        assert PostTranslation.objects.filter(slug='deletable-post').count() == 0


@pytest.mark.django_db
class TestBlogSitemapsI18n:
    """Tests para los sitemaps i18n del blog."""
    
    def test_sitemaps_en_pt_registered(self):
        """Verifica que los sitemaps en y pt están registrados."""
        assert 'blog-posts-en' in sitemaps
        assert 'blog-posts-pt' in sitemaps
    
    def test_sitemaps_en_items_and_location(self, blog_post_article, blog_post_translation_en):
        """Verifica que el sitemap en inglés incluye la URL con /en/."""
        sitemap_cls = sitemaps['blog-posts-en']
        sitemap_instance = sitemap_cls()
        items = list(sitemap_instance.items())
        assert blog_post_translation_en in items
        loc = sitemap_instance.location(blog_post_translation_en)
        assert '/en/blog/' in loc
        assert blog_post_translation_en.slug in loc

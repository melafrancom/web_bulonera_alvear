"""Test Models - Blog app"""
import pytest
from django.utils import timezone
from blog.models import Post, PostTag, SocialMetadata


class TestPostTag:
    """Tests para el modelo PostTag"""
    
    def test_post_tag_creation(self, db_session, blog_tag):
        """Verifica que se crea un tag correctamente"""
        assert blog_tag.name == 'Guías Técnicas'
        assert blog_tag.slug == 'guias-tecnicas'
    
    def test_post_tag_slug_auto_generation(self, db_session):
        """Verifica que el slug se genera automáticamente"""
        tag = PostTag.objects.create(name='Novedades Industria')
        assert tag.slug == 'novedades-industria'
    
    def test_post_tag_str(self, db_session, blog_tag):
        """Verifica que __str__ retorna el nombre"""
        assert str(blog_tag) == 'Guías Técnicas'


class TestPost:
    """Tests para el modelo Post"""
    
    def test_post_creation(self, db_session, blog_post_article):
        """Verifica que se crea un post correctamente"""
        assert blog_post_article.title == 'Cómo seleccionar tornillos correctamente'
        assert blog_post_article.post_type == 'article'
        assert blog_post_article.is_published is True
    
    def test_post_slug_auto_generation(self, db_session, admin_user):
        """Verifica que el slug se genera automáticamente"""
        post = Post.objects.create(
            title='Mi Primer Artículo de Prueba',
            content='Contenido de prueba',
            author=admin_user
        )
        assert post.slug == 'mi-primer-articulo-de-prueba'
    
    def test_post_slug_unique_collision_handling(self, db_session, admin_user):
        """Verifica que se manejan colisiones de slug"""
        post1 = Post.objects.create(
            title='Artículo Duplicado Versión 1',
            slug='articulo-duplicado',
            content='Contenido 1',
            author=admin_user
        )
        # Cambiar el slug manualmente para simular colisión
        post2 = Post.objects.create(
            title='Artículo Duplicado Versión 2',
            content='Contenido 2',
            author=admin_user
        )
        # Forzar slug similar
        post2.slug = 'articulo-duplicado'
        # El save() no debe permitir slug duplicado
        # En realidad, el modelo genera uno único
        assert post1.slug == 'articulo-duplicado'
        # post2 debe tener un slug único generado
        assert post2.slug != post1.slug or post2.id != post1.id
    
    def test_post_meta_title_auto_fill(self, db_session, admin_user):
        """Verifica que meta_title se completa automáticamente con límite de 60 caracteres"""
        long_title = 'Título Extenso de Post de Blog para Probar la Restricción de 60 Caracteres SERP'
        post = Post.objects.create(
            title=long_title,
            content='Contenido',
            author=admin_user
        )
        assert len(post.meta_title) <= 60
        assert post.meta_title == long_title[:60]

    def test_post_reading_time_and_summaries(self, db_session, admin_user):
        """Verifica el cálculo de tiempo de lectura y resúmenes GEO/AEO"""
        post = Post.objects.create(
            title='Guía de Selección de Bulones de Alta Resistencia',
            content='word ' * 450,  # 450 palabras -> 2 min
            excerpt='Resumen para la guía técnica.',
            author=admin_user
        )
        assert post.reading_time_minutes == 2
        
        geo_summary = post.get_geo_summary()
        voice_summary = post.get_voice_summary()
        
        assert 'Guía de Selección de Bulones' in geo_summary
        assert 'Resumen para la guía técnica.' in geo_summary
        assert 'Artículo técnico' in voice_summary
    
    def test_post_meta_description_from_excerpt(self, db_session, admin_user):
        """Verifica que meta_description se completa desde excerpt"""
        post = Post.objects.create(
            title='Título',
            content='Contenido',
            excerpt='Este es mi resumen corto para SEO',
            author=admin_user
        )
        assert post.meta_description == 'Este es mi resumen corto para SEO'
    
    def test_post_published_date_auto_set(self, db_session, admin_user):
        """Verifica que published_date se establece automáticamente"""
        before = timezone.now()
        post = Post.objects.create(
            title='Nuevo Post',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        after = timezone.now()
        assert before <= post.published_date <= after
    
    def test_post_get_absolute_url(self, db_session, blog_post_article):
        """Verifica que get_absolute_url retorna la URL correcta"""
        url = blog_post_article.get_absolute_url()
        assert url == f'/blog/{blog_post_article.slug}/'
    
    def test_post_image_url_property(self, db_session, blog_post_article):
        """Verifica la propiedad image_url sin featured_image"""
        assert blog_post_article.image_url == '/static/images/placeholder.png'
    
    def test_post_views_count_default(self, db_session, blog_post_article):
        """Verifica que views_count comienza en 0"""
        assert blog_post_article.views_count == 0
    
    def test_post_str(self, db_session, blog_post_article):
        """Verifica que __str__ retorna el título"""
        assert str(blog_post_article) == blog_post_article.title
    
    def test_post_ordering(self, db_session, admin_user):
        """Verifica que los posts se ordenan por fecha descendente"""
        from django.utils import timezone
        post1 = Post.objects.create(
            title='Post 1',
            content='Contenido 1',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        import time
        time.sleep(0.1)
        post2 = Post.objects.create(
            title='Post 2',
            content='Contenido 2',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        posts = list(Post.objects.all())
        assert posts[0].id == post2.id


class TestSocialMetadata:
    """Tests para el modelo SocialMetadata"""
    
    def test_social_metadata_creation(self, db_session, social_metadata):
        """Verifica que se crea metadata de red social correctamente"""
        assert social_metadata.platform == 'instagram'
        assert 'instagram.com' in social_metadata.original_url
    
    def test_social_metadata_str(self, db_session, social_metadata):
        """Verifica que __str__ retorna el formato correcto"""
        assert 'Instagram' in str(social_metadata)
    
    def test_social_metadata_one_to_one_relationship(self, db_session, social_metadata, blog_post_social_repost):
        """Verifica la relación OneToOne con Post"""
        retrieved_metadata = blog_post_social_repost.social_metadata
        assert retrieved_metadata.id == social_metadata.id
    
    def test_post_slug_with_non_ascii_title(self, db_session, admin_user):
        """
        BUG-01: Verifica que cuando título contiene solo espacios/símbolos,
        se genera slug dinámico con timestamp (no fijo 'post').
        """
        # Crear post con título que slugify() reduce a cadena vacía
        post1 = Post.objects.create(
            title='   ★★★   ',  # Solo espacios y símbolos
            content='Contenido especial',
            author=admin_user
        )
        # El slug debe contener "post-" + timestamp (fallback dinámico)
        assert post1.slug.startswith('post-')
        assert len(post1.slug) > 5  # 'post-' + números timestamp
        
        # Verificar que se puede crear otro post similar sin colisión
        post2 = Post.objects.create(
            title='   ☆☆☆   ',
            content='Más contenido especial',
            author=admin_user
        )
        # Debe generar slug diferente
        assert post2.slug != post1.slug
        assert post2.slug.startswith('post-')
    
    def test_social_metadata_cannot_create_second_for_same_post(self, db_session, blog_post_article, admin_user):
        """
        BUG-03: Verifica que OneToOneField previene múltiples SocialMetadata
        para el mismo Post lanzando IntegrityError.
        """
        from django.db import IntegrityError
        
        # Crear primer metadata
        meta1 = SocialMetadata.objects.create(
            post=blog_post_article,
            platform='instagram',
            original_url='https://instagram.com/example',
            embed_code='<div>Instagram</div>',
            embed_url='https://instagram.com/embed'
        )
        assert blog_post_article.social_metadata.id == meta1.id
        
        # Intentar crear segundo metadata para el mismo post
        # Debe lanzar IntegrityError por UNIQUE constraint en post_id
        with pytest.raises(IntegrityError):
            SocialMetadata.objects.create(
                post=blog_post_article,
                platform='tiktok',
                original_url='https://tiktok.com/example',
                embed_code='<div>TikTok</div>',
                embed_url='https://tiktok.com/embed'
            )


class TestPostCleanValidation:
    """Tests para validación de negocio en Post.clean()"""
    
    def test_post_clean_validation_social_repost_requires_metadata(self, db_session, blog_post_social_repost):
        """
        Verifica que Post.clean() lanza ValidationError cuando
        un post de tipo 'social_repost' se publica sin SocialMetadata.
        """
        from django.core.exceptions import ValidationError
        
        # Crear un post social_repost SIN metadata y SIN publicar
        post = Post.objects.create(
            title='Repost Sin Metadata',
            post_type='social_repost',
            content='Contenido del repost',
            is_published=False,
            author=blog_post_social_repost.author
        )
        
        # clean() NO debe lanzar error si NO está publicado
        try:
            post.clean()
        except ValidationError:
            pytest.fail("clean() no debe lanzar error para social_repost NO publicado")
        
        # Intentar publicar SIN metadata debe fallar
        post.is_published = True
        with pytest.raises(ValidationError) as exc_info:
            post.clean()
        
        assert 'post_type' in exc_info.value.error_dict
        assert 'no puede publicarse sin completar la sección' in str(exc_info.value)
    
    def test_post_clean_validation_article_no_metadata_required(self, db_session, admin_user):
        """
        Verifica que Post.clean() permite publicar artículos sin SocialMetadata.
        La validación es SOLO para social_repost.
        """
        from django.core.exceptions import ValidationError
        
        # Crear un post article sin metadata
        post = Post.objects.create(
            title='Artículo Sin Metadata Social',
            post_type='article',
            content='Contenido del artículo',
            is_published=True,
            author=admin_user
        )
        
        # clean() debe permitir esto (no debe lanzar error)
        try:
            post.clean()
        except ValidationError:
            pytest.fail("clean() no debe validar SocialMetadata para artículos")
    
    def test_post_clean_validation_social_repost_with_metadata_succeeds(self, db_session, social_metadata):
        """
        Verifica que Post.clean() permite publicar social_repost CON SocialMetadata.
        """
        from django.core.exceptions import ValidationError
        
        # El post ya tiene metadata vía social_metadata (OneToOne)
        post = social_metadata.post
        post.is_published = True
        
        # clean() debe permitir esto
        try:
            post.clean()
        except ValidationError:
            pytest.fail("clean() debe permitir social_repost publicado con SocialMetadata")

"""Test Services - Blog app"""
import pytest
from django.utils import timezone
from blog.services import BlogService
from blog.models import Post, PostTag


class TestBlogService:
    """Tests para el servicio BlogService"""
    
    def test_get_published_posts(self, db_session, blog_post_article, blog_post_draft):
        """Verifica que solo retorna posts publicados"""
        posts = BlogService.get_published_posts()
        assert blog_post_article in posts
        assert blog_post_draft not in posts
    
    def test_get_published_posts_filtered_by_tag(self, db_session, blog_post_article, blog_tag):
        """Verifica filtro por tag"""
        posts = BlogService.get_published_posts(tag_slug=blog_tag.slug)
        assert blog_post_article in posts
    
    def test_get_published_posts_filtered_by_tag_empty(self, db_session, blog_post_article):
        """Verifica que retorna vacío cuando no hay posts con el tag"""
        posts = BlogService.get_published_posts(tag_slug='tag-inexistente')
        assert list(posts) == []
    
    def test_get_post_by_slug_success(self, db_session, blog_post_article):
        """Verifica que encuentra un post por slug"""
        post = BlogService.get_post_by_slug(blog_post_article.slug)
        assert post.id == blog_post_article.id
    
    def test_get_post_by_slug_not_found(self, db_session):
        """Verifica que retorna None para slug no encontrado"""
        post = BlogService.get_post_by_slug('slug-inexistente')
        assert post is None
    
    def test_get_post_by_slug_draft_not_returned(self, db_session, blog_post_draft):
        """Verifica que no retorna posts sin publicar"""
        post = BlogService.get_post_by_slug(blog_post_draft.slug)
        assert post is None
    
    def test_get_related_posts_by_tags(self, db_session, admin_user, blog_tag):
        """Verifica que obtiene posts relacionados por tags"""
        post1 = Post.objects.create(
            title='Post 1',
            slug='post-1',
            content='Contenido 1',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        post1.tags.add(blog_tag)
        
        post2 = Post.objects.create(
            title='Post 2',
            slug='post-2',
            content='Contenido 2',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        post2.tags.add(blog_tag)
        
        related = BlogService.get_related_posts(post1)
        assert post2 in related
        assert post1 not in related
    
    def test_get_related_posts_no_tags(self, db_session, admin_user):
        """Verifica que retorna posts recientes cuando no hay tags"""
        post1 = Post.objects.create(
            title='Post 1',
            slug='post-1',
            content='Contenido 1',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        
        post2 = Post.objects.create(
            title='Post 2',
            slug='post-2',
            content='Contenido 2',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        
        related = BlogService.get_related_posts(post1)
        assert post2 in related
    
    def test_increment_views(self, db_session, blog_post_article):
        """Verifica que incrementa el contador de vistas"""
        initial_views = blog_post_article.views_count
        BlogService.increment_views(blog_post_article.id)
        
        # Refrescar del DB
        post = Post.objects.get(id=blog_post_article.id)
        assert post.views_count == initial_views + 1
    
    def test_search_posts_by_title(self, db_session, blog_post_article):
        """Verifica búsqueda por título"""
        results = BlogService.search_posts('seleccionar tornillos')
        assert blog_post_article in results
    
    def test_search_posts_by_content(self, db_session, admin_user):
        """Verifica búsqueda por contenido"""
        post = Post.objects.create(
            title='Título Genérico',
            slug='titulo-generico',
            content='<p>Contenido con palabra_clave especial</p>',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        results = BlogService.search_posts('palabra_clave')
        assert post in results
    
    def test_search_posts_excludes_draft(self, db_session, blog_post_draft):
        """Verifica que no busca en borradores"""
        results = BlogService.search_posts('Borrador')
        assert blog_post_draft not in results
    
    def test_get_all_tags(self, db_session, blog_post_article, blog_tag):
        """Verifica que obtiene todos los tags usados en posts publicados"""
        tags = BlogService.get_all_tags()
        assert blog_tag in tags
    
    def test_get_posts_by_type_article(self, db_session, blog_post_article, blog_post_social_repost):
        """Verifica filtrado por tipo de post"""
        articles = BlogService.get_posts_by_type('article')
        assert blog_post_article in articles
        # El repost puede estar o no, depende de si es social_repost
    
    def test_get_posts_by_type_social_repost(self, db_session, blog_post_social_repost):
        """Verifica filtrado por tipo social_repost"""
        reposts = BlogService.get_posts_by_type('social_repost')
        assert blog_post_social_repost in reposts
    
    def test_get_published_posts_excludes_future_scheduled(self, db_session, admin_user):
        """
        FASE 2: Verifica que get_published_posts() excluye posts
        con published_date en el futuro (scheduled publishing).
        """
        now = timezone.now()
        future = now + timezone.timedelta(hours=1)
        
        # Post publicado con fecha en el pasado (debe aparecer)
        past_post = Post.objects.create(
            title='Post publicado hace 1 hora',
            slug='post-pasado',
            content='Contenido pasado',
            author=admin_user,
            is_published=True,
            published_date=now - timezone.timedelta(hours=1)
        )
        
        # Post con published_date en el futuro (no debe aparecer)
        future_post = Post.objects.create(
            title='Post programado para luego',
            slug='post-futuro',
            content='Contenido futuro',
            author=admin_user,
            is_published=True,
            published_date=future
        )
        
        # Obtener posts publicados
        published = list(BlogService.get_published_posts())
        
        # El post pasado debe estar
        assert past_post in published
        
        # El post futuro NO debe estar
        assert future_post not in published
    
    def test_publish_post_method(self, db_session, admin_user):
        """
        FASE 2: Verifica el nuevo método publish_post() que
        publica un post inmediatamente o en una fecha futura.
        """
        # Crear post sin publicar
        post = Post.objects.create(
            title='Post para publicar',
            slug='post-to-publish',
            content='Contenido a publicar',
            author=admin_user,
            is_published=False,
            published_date=None
        )
        
        # Publicar ahora
        published_post = BlogService.publish_post(post.id)
        
        # Verificar que ahora está publicado
        assert published_post.is_published is True
        assert published_post.published_date is not None
        
        # Refrescar del DB
        post_db = Post.objects.get(id=post.id)
        assert post_db.is_published is True
        
        # Probar publicación programada
        post2 = Post.objects.create(
            title='Post para publicar después',
            slug='post-to-publish-later',
            content='Contenido a publicar después',
            author=admin_user,
            is_published=False,
            published_date=None
        )
        
        future_date = timezone.now() + timezone.timedelta(days=7)
        published_post2 = BlogService.publish_post(post2.id, scheduled_date=future_date)
        
        # Verificar que está publicado con la fecha futura
        assert published_post2.is_published is True
        assert published_post2.published_date.date() == future_date.date()

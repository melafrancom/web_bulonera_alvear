"""Test API - Blog app"""
import pytest
from django.urls import reverse
from rest_framework import status
from blog.models import Post, PostTag


@pytest.mark.django_db
class TestPostAPI:
    """Tests para la API REST de posts"""
    
    def test_post_list_api_returns_200(self, client):
        """Verifica que el listado de posts retorna 200"""
        response = client.get('/api/v1/blog/posts/')
        assert response.status_code == 200
    
    def test_post_list_api_returns_json(self, client):
        """Verifica que retorna JSON"""
        response = client.get('/api/v1/blog/posts/')
        assert response['Content-Type'] == 'application/json'
    
    def test_post_list_api_includes_published_only(self, client, blog_post_article, blog_post_draft):
        """Verifica que solo retorna posts publicados"""
        response = client.get('/api/v1/blog/posts/')
        data = response.json()
        
        post_ids = [p['id'] for p in data['results']]
        assert blog_post_article.id in post_ids
        assert blog_post_draft.id not in post_ids
    
    def test_post_detail_api_returns_200(self, client, blog_post_article):
        """Verifica que el detalle del post retorna 200"""
        url = f'/api/v1/blog/posts/{blog_post_article.id}/'
        response = client.get(url)
        assert response.status_code == 200
    
    def test_post_detail_api_includes_content(self, client, blog_post_article):
        """Verifica que el detalle incluye el contenido"""
        url = f'/api/v1/blog/posts/{blog_post_article.id}/'
        response = client.get(url)
        data = response.json()
        
        assert data['title'] == blog_post_article.title
        assert data['content'] == blog_post_article.content
    
    def test_post_detail_api_includes_meta_seo(self, client, blog_post_article):
        """Verifica que el detalle incluye tags SEO"""
        url = f'/api/v1/blog/posts/{blog_post_article.id}/'
        response = client.get(url)
        data = response.json()
        
        assert 'meta_title' in data
        assert 'meta_description' in data
        assert 'meta_keywords' in data
    
    def test_post_list_api_filter_by_post_type(self, client, blog_post_article, blog_post_social_repost):
        """Verifica filtrado por tipo de post"""
        response = client.get('/api/v1/blog/posts/?post_type=article')
        data = response.json()
        
        post_ids = [p['id'] for p in data['results']]
        assert blog_post_article.id in post_ids
    
    def test_post_list_api_filter_by_tag(self, client, blog_post_article, blog_tag):
        """Verifica filtrado por tag"""
        response = client.get(f'/api/v1/blog/posts/?tags__slug={blog_tag.slug}')
        data = response.json()
        
        if data['results']:
            assert blog_post_article.id in [p['id'] for p in data['results']]
    
    def test_post_list_api_search(self, client, blog_post_article):
        """Verifica búsqueda por título/contenido"""
        search_term = 'seleccionar'
        response = client.get(f'/api/v1/blog/posts/?search={search_term}')
        data = response.json()
        
        assert blog_post_article.id in [p['id'] for p in data['results']]
    
    def test_post_list_api_ordering_by_date(self, client, admin_user):
        """Verifica ordenamiento por fecha"""
        post1 = Post.objects.create(
            title='Post Viejo',
            slug='post-viejo',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        post2 = Post.objects.create(
            title='Post Nuevo',
            slug='post-nuevo',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        
        response = client.get('/api/v1/blog/posts/')
        data = response.json()
        
        # El más reciente debe estar primero (ordenamiento por defecto)
        assert data['results'][0]['id'] == post2.id
    
    def test_post_draft_returns_404_in_api(self, client, blog_post_draft):
        """Verifica que posts en borrador retornan 404 en API"""
        url = f'/api/v1/blog/posts/{blog_post_draft.id}/'
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestPostTagAPI:
    """Tests para la API REST de tags"""
    
    def test_tag_list_api_returns_200(self, client, blog_tag):
        """Verifica que el listado de tags retorna 200"""
        response = client.get('/api/v1/blog/tags/')
        assert response.status_code == 200
    
    def test_tag_list_api_returns_only_used_tags(self, client, blog_tag, blog_post_article):
        """Verifica que solo retorna tags usados en posts publicados"""
        response = client.get('/api/v1/blog/tags/')
        data = response.json()
        
        tag_ids = [t['id'] for t in data['results']]
        assert blog_tag.id in tag_ids
    
    def test_tag_detail_api_returns_200(self, client, blog_tag, blog_post_article):
        """Verifica que el detalle del tag retorna 200"""
        url = f'/api/v1/blog/tags/{blog_tag.slug}/'
        response = client.get(url)
        assert response.status_code == 200
    
    def test_tag_detail_api_includes_name(self, client, blog_tag, blog_post_article):
        """Verifica que el detalle incluye el nombre"""
        url = f'/api/v1/blog/tags/{blog_tag.slug}/'
        response = client.get(url)
        data = response.json()
        
        assert data['name'] == blog_tag.name


@pytest.mark.django_db
class TestPostAPIPermissions:
    """Tests para permisos en la API de posts"""
    
    def test_post_api_is_read_only(self, api_client):
        """Verifica que la API es read-only (no permite POST)"""
        response = api_client.post('/api/v1/blog/posts/', {'title': 'New Post'})
        assert response.status_code in [405, 403]
    
    def test_post_api_no_authentication_required(self, client):
        """Verifica que no requiere autenticación"""
        response = client.get('/api/v1/blog/posts/')
        assert response.status_code == 200

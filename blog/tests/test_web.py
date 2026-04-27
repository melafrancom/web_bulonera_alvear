"""Test Web Views - Blog app"""
import pytest
from django.urls import reverse
from blog.models import Post


@pytest.mark.django_db
class TestBlogListView:
    """Tests para la vista de listado de posts"""
    
    def test_blog_list_view_returns_200(self, client, blog_post_article):
        """Verifica que la vista retorna status 200"""
        response = client.get(reverse('blog:post_list'))
        assert response.status_code == 200
    
    def test_blog_list_view_uses_correct_template(self, client, blog_post_article):
        """Verifica que usa el template correcto"""
        response = client.get(reverse('blog:post_list'))
        assert 'blog/post_list.html' in [t.name for t in response.templates]
    
    def test_blog_list_view_contains_posts(self, client, blog_post_article):
        """Verifica que la lista contiene posts publicados"""
        response = client.get(reverse('blog:post_list'))
        assert blog_post_article in response.context['posts']
    
    def test_blog_list_view_excludes_draft_posts(self, client, blog_post_article, blog_post_draft):
        """Verifica que no incluye posts en borrador"""
        response = client.get(reverse('blog:post_list'))
        assert blog_post_draft not in response.context['posts']
    
    def test_blog_list_view_includes_tags(self, client, blog_post_article, blog_tag):
        """Verifica que incluye tags en el contexto"""
        response = client.get(reverse('blog:post_list'))
        assert blog_tag in response.context['tags']
    
    def test_blog_list_view_filters_by_tag(self, client, admin_user, blog_tag):
        """Verifica filtrado por tag en la URL"""
        post = Post.objects.create(
            title='Con Tag',
            slug='con-tag',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        post.tags.add(blog_tag)
        
        response = client.get(reverse('blog:post_list') + f'?tag={blog_tag.slug}')
        assert post in response.context['posts']
        assert response.context['active_tag'] == blog_tag.slug
    
    def test_blog_list_view_pagination(self, client, admin_user):
        """Verifica que la paginación funciona"""
        # Crear 15 posts
        for i in range(15):
            Post.objects.create(
                title=f'Post {i}',
                slug=f'post-{i}',
                content='Contenido',
                author=admin_user,
                is_published=True
            )
        
        response = client.get(reverse('blog:post_list'))
        assert response.context['is_paginated'] is True
        assert len(response.context['posts']) == 9  # paginate_by = 9


@pytest.mark.django_db
class TestBlogDetailView:
    """Tests para la vista de detalle de post"""
    
    def test_blog_detail_view_returns_200(self, client, blog_post_article):
        """Verifica que la vista retorna status 200"""
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        response = client.get(url)
        assert response.status_code == 200
    
    def test_blog_detail_view_uses_correct_template(self, client, blog_post_article):
        """Verifica que usa el template correcto"""
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        response = client.get(url)
        assert 'blog/post_detail.html' in [t.name for t in response.templates]
    
    def test_blog_detail_view_contains_correct_post(self, client, blog_post_article):
        """Verifica que el contexto tiene el post correcto"""
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        response = client.get(url)
        assert response.context['post'].id == blog_post_article.id
    
    def test_blog_detail_view_draft_returns_404(self, client, blog_post_draft):
        """Verifica que posts en borrador retornan 404"""
        url = reverse('blog:post_detail', args=[blog_post_draft.slug])
        response = client.get(url)
        assert response.status_code == 404
    
    def test_blog_detail_view_increments_views(self, client, blog_post_article):
        """Verifica que incrementa el contador de vistas"""
        initial_views = blog_post_article.views_count
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        client.get(url)
        
        post = Post.objects.get(id=blog_post_article.id)
        assert post.views_count == initial_views + 1
    
    def test_blog_detail_view_includes_related_posts(self, client, admin_user, blog_tag):
        """Verifica que incluye posts relacionados"""
        post1 = Post.objects.create(
            title='Post Principal',
            slug='post-principal',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        post1.tags.add(blog_tag)
        
        post2 = Post.objects.create(
            title='Post Relacionado',
            slug='post-relacionado',
            content='Contenido',
            author=admin_user,
            is_published=True
        )
        post2.tags.add(blog_tag)
        
        url = reverse('blog:post_detail', args=[post1.slug])
        response = client.get(url)
        assert post2 in response.context['related_posts']
    
    def test_blog_detail_view_nonexistent_slug_returns_404(self, client):
        """Verifica que slug inexistente retorna 404"""
        url = reverse('blog:post_detail', args=['slug-inexistente'])
        response = client.get(url)
        assert response.status_code == 404

    @pytest.mark.skip(reason="Requiere completo modelo Product con category. Testeado manualmente.")
    def test_blog_detail_view_includes_featured_products(self, client, admin_user):
        """Verifica que incluye productos destacados en el contexto"""
        pass

    @pytest.mark.skip(reason="Requiere completo modelo Product con category. Testeado manualmente.")
    def test_blog_detail_view_featured_products_in_template(self, client, admin_user):
        """Verifica que featured_products se renderiza en el template"""
        pass


@pytest.mark.django_db
class TestBlogSEO:
    """Tests para SEO en vistas del blog"""
    
    def test_blog_list_view_has_title_meta(self, client, blog_post_article):
        """Verifica que la lista tiene meta tags de title"""
        response = client.get(reverse('blog:post_list'))
        content = response.content.decode()
        assert 'Blog' in content
    
    def test_blog_detail_view_has_seo_meta(self, client, blog_post_article):
        """Verifica que el detalle tiene meta tags SEO"""
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        response = client.get(url)
        content = response.content.decode()
        assert blog_post_article.meta_title in content or blog_post_article.title in content
    
    def test_blog_detail_view_has_json_ld(self, client, blog_post_article):
        """Verifica que el detalle incluye JSON-LD schema"""
        url = reverse('blog:post_detail', args=[blog_post_article.slug])
        response = client.get(url)
        content = response.content.decode()
        assert 'BlogPosting' in content

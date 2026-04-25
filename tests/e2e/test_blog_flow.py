"""
Tests E2E: Flujo completo del Blog.
Simula el journey de un usuario anónimo que:
1. Visita la lista del blog
2. Hace click en un post (navega al detalle)
3. Verifica que el contenido y SEO son correctos
4. Verifica que los posts relacionados se muestran
"""
import pytest
from django.urls import reverse
from django.utils import timezone
from blog.models import Post, PostTag


@pytest.mark.django_db
class TestBlogUserJourney:
    """
    E2E: Flujo completo del usuario en la app blog.
    Cada test representa UN paso del journey.
    """

    @pytest.fixture(autouse=True)
    def setup_blog_content(self, admin_user):
        """
        Setup: Crea contenido de blog realista para los tests de flujo.
        """
        self.tag_tornillos = PostTag.objects.create(
            name='Tornillos', slug='tornillos'
        )
        self.tag_tutoriales = PostTag.objects.create(
            name='Tutoriales', slug='tutoriales'
        )
        self.post_main = Post.objects.create(
            title='Cómo elegir el tornillo correcto',
            slug='como-elegir-tornillo-correcto',
            content='<p>Guía completa para seleccionar tornillos según aplicación.</p>',
            excerpt='Aprende a seleccionar el tornillo adecuado para cada trabajo.',
            meta_title='Guía: Cómo Elegir el Tornillo Correcto | Bulonera Alvear',
            meta_description='Aprende a seleccionar tornillos correctamente.',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        self.post_main.tags.add(self.tag_tornillos, self.tag_tutoriales)

        self.post_related = Post.objects.create(
            title='Tipos de Tuercas: Guía Completa',
            slug='tipos-de-tuercas-guia-completa',
            content='<p>Todo sobre los tipos de tuercas disponibles.</p>',
            excerpt='Guía completa sobre tipos de tuercas.',
            author=admin_user,
            is_published=True,
            published_date=timezone.now() - timezone.timedelta(days=1)
        )
        self.post_related.tags.add(self.tag_tornillos)

    # --- PASO 1: Usuario visita la lista del blog ---

    def test_step1_blog_list_loads(self, client):
        """E2E Paso 1: La lista del blog carga correctamente."""
        response = client.get(reverse('blog:post_list'))
        assert response.status_code == 200

    def test_step1_blog_list_shows_published_posts(self, client):
        """E2E Paso 1: La lista muestra los posts publicados."""
        response = client.get(reverse('blog:post_list'))
        assert self.post_main in response.context['posts']

    def test_step1_blog_list_shows_tags_for_filtering(self, client):
        """E2E Paso 1: La lista expone tags para filtrar."""
        response = client.get(reverse('blog:post_list'))
        assert self.tag_tornillos in response.context['tags']

    def test_step1_blog_list_tag_filter_works(self, client):
        """E2E Paso 1: El filtro por tag funciona y reduce resultados."""
        url = reverse('blog:post_list') + f'?tag={self.tag_tutoriales.slug}'
        response = client.get(url)
        # Solo post_main tiene 'tutoriales', post_related no
        assert self.post_main in response.context['posts']
        assert self.post_related not in response.context['posts']
        assert response.context['active_tag'] == self.tag_tutoriales.slug

    # --- PASO 2: Usuario navega al detalle de un post ---

    def test_step2_blog_detail_loads(self, client):
        """E2E Paso 2: La vista de detalle carga correctamente."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        assert response.status_code == 200

    def test_step2_blog_detail_shows_correct_content(self, client):
        """E2E Paso 2: El detalle muestra el contenido del post correcto."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        content = response.content.decode()
        assert self.post_main.title in content
        assert 'seleccionar tornillos' in content.lower()

    def test_step2_blog_detail_increments_views_counter(self, client):
        """E2E Paso 2: Visitar el detalle incrementa el contador de vistas."""
        initial_views = self.post_main.views_count
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        client.get(url)

        self.post_main.refresh_from_db()
        assert self.post_main.views_count == initial_views + 1

    def test_step2_blog_detail_shows_related_posts(self, client):
        """E2E Paso 2: El detalle muestra posts relacionados por tag."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        assert self.post_related in response.context['related_posts']
        assert self.post_main not in response.context['related_posts']

    # --- PASO 3: Verificación de SEO en la respuesta HTML ---

    def test_step3_blog_detail_has_seo_title(self, client):
        """E2E Paso 3: El HTML incluye el meta title SEO correcto."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        content = response.content.decode()
        assert self.post_main.meta_title in content

    def test_step3_blog_detail_has_canonical_url(self, client):
        """E2E Paso 3: El HTML incluye canonical URL."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        content = response.content.decode()
        assert 'rel="canonical"' in content

    def test_step3_blog_detail_has_json_ld_schema(self, client):
        """E2E Paso 3: El HTML incluye JSON-LD BlogPosting schema."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        content = response.content.decode()
        assert '"BlogPosting"' in content
        assert '"headline"' in content

    def test_step3_blog_detail_has_og_tags(self, client):
        """E2E Paso 3: El HTML incluye OpenGraph tags para compartir en redes."""
        url = reverse('blog:post_detail', args=[self.post_main.slug])
        response = client.get(url)
        content = response.content.decode()
        assert 'property="og:title"' in content
        assert 'property="og:description"' in content
        assert 'property="og:type"' in content


@pytest.mark.django_db
class TestBlogAPIUserJourney:
    """
    E2E: Flujo completo del usuario en la API del blog (para PWA).
    Replica el mismo journey pero via JSON.
    """

    @pytest.fixture(autouse=True)
    def setup_blog_content(self, admin_user):
        """Setup compartido: mismo contenido que el journey web."""
        self.tag = PostTag.objects.create(name='Industria', slug='industria')
        self.post = Post.objects.create(
            title='Normas ISO para Bulones',
            slug='normas-iso-bulones',
            content='<p>Guía sobre normas ISO aplicadas a bulones.</p>',
            excerpt='Todo sobre normas ISO en bulonería.',
            meta_title='Normas ISO Bulones | Bulonera Alvear',
            meta_description='Guía completa sobre normas ISO para bulones.',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        self.post.tags.add(self.tag)

    def test_api_step1_list_returns_published(self, client):
        """E2E API Paso 1: La lista retorna posts publicados con paginación."""
        response = client.get('/api/v1/blog/posts/')
        data = response.json()
        assert response.status_code == 200
        assert 'results' in data
        assert 'count' in data
        post_ids = [p['id'] for p in data['results']]
        assert self.post.id in post_ids

    def test_api_step2_detail_returns_full_data(self, client):
        """E2E API Paso 2: El detalle retorna todos los campos necesarios para la PWA."""
        url = f'/api/v1/blog/posts/{self.post.id}/'
        response = client.get(url)
        data = response.json()
        assert response.status_code == 200
        # Campos mínimos que la PWA necesita para renderizar
        required_fields = [
            'id', 'title', 'slug', 'content', 'excerpt',
            'meta_title', 'meta_description', 'image_url',
            'published_date', 'tags', 'social_metadata'
        ]
        for field in required_fields:
            assert field in data, f"Campo '{field}' faltante en la respuesta de la API"

    def test_api_step2_detail_increments_views(self, client):
        """E2E API Paso 2: GET al detalle incrementa vistas (paridad con web)."""
        initial_views = self.post.views_count
        client.get(f'/api/v1/blog/posts/{self.post.id}/')
        self.post.refresh_from_db()
        assert self.post.views_count == initial_views + 1

    def test_api_step3_related_endpoint_works(self, client, admin_user):
        """E2E API Paso 3: El endpoint de relacionados retorna datos válidos."""
        related_post = Post.objects.create(
            title='Bulones de Alta Resistencia',
            slug='bulones-alta-resistencia',
            content='Contenido sobre bulones de alta resistencia.',
            author=admin_user,
            is_published=True,
            published_date=timezone.now()
        )
        related_post.tags.add(self.tag)

        url = f'/api/v1/blog/posts/{self.post.id}/related/'
        response = client.get(url)
        data = response.json()
        assert response.status_code == 200
        related_ids = [p['id'] for p in data]
        assert related_post.id in related_ids
        assert self.post.id not in related_ids

"""Blog Sitemaps - XML sitemap generation for SEO"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from blog.models import Post, PostTag
from blog.services import BlogService


class BlogPostSitemap(Sitemap):
    """
    Genera un sitemap XML de todos los posts publicados.
    Necesario para descubrimiento por motores de búsqueda.
    
    Características:
    - Incluye priority y changefreq para indicar importancia
    - Ordena por última modificación para crawlers inteligentes
    - Usa BlogService para obtener posts publicados con filtro de date
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'
    
    def items(self):
        """Retorna todos los posts publicados y accesibles."""
        return BlogService.get_published_posts()
    
    def lastmod(self, item: Post) -> timezone.datetime:
        """Retorna la última modificación del post."""
        return item.modified_date
    
    def location(self, item: Post) -> str:
        """Retorna la URL absoluta del post."""
        return reverse('blog:post_detail', kwargs={'slug': item.slug})


class BlogTagSitemap(Sitemap):
    """
    Genera un sitemap XML de todas las páginas de tags.
    Importante para facilitar indexación de taxonomía.
    
    Características:
    - Priority menor que posts individuales (estos son agregadores)
    - changefreq=daily porque nuevos posts afectan contenido del tag
    - lastmod basado en el post más reciente del tag
    """
    changefreq = 'daily'
    priority = 0.6
    protocol = 'https'
    
    def items(self):
        """Retorna todos los tags con posts publicados."""
        return BlogService.get_all_tags()
    
    def lastmod(self, item: PostTag) -> timezone.datetime:
        """
        Retorna la fecha del post más reciente con este tag.
        Si no hay posts publicados, retorna ahora.
        """
        latest_post = item.posts.filter(
            is_published=True
        ).order_by('-modified_date').first()
        return latest_post.modified_date if latest_post else timezone.now()
    
    def location(self, item: PostTag) -> str:
        """Retorna la URL de la página de tag."""
        return reverse('blog:post_list') + f'?tag={item.slug}'


# Registro de sitemaps para pasarlo a Django Sitemap framework
sitemaps = {
    'blog-posts': BlogPostSitemap,
    'blog-tags': BlogTagSitemap,
}

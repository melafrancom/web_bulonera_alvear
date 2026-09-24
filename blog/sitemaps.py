"""Blog Sitemaps - XML sitemap generation for SEO"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from blog.models import Post, PostTag, PostTranslation
from blog.services import BlogService


class BlogPostSitemap(Sitemap):
    """
    Genera un sitemap XML de todos los posts publicados en español.
    Necesario para descubrimiento por motores de búsqueda.
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


class BlogPostEnglishSitemap(Sitemap):
    """
    Sitemap de posts del blog traducidos al inglés.
    Solo incluye posts con PostTranslation(language='en').
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'
    
    def items(self):
        return PostTranslation.objects.filter(
            language='en',
            post__is_published=True,
            post__published_date__lte=timezone.now()
        ).select_related('post')
    
    def lastmod(self, item):
        return item.modified_date
    
    def location(self, item):
        return item.get_absolute_url()


class BlogPostPortugueseSitemap(Sitemap):
    """
    Sitemap de posts del blog traducidos al portugués.
    Solo incluye posts con PostTranslation(language='pt').
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'
    
    def items(self):
        return PostTranslation.objects.filter(
            language='pt',
            post__is_published=True,
            post__published_date__lte=timezone.now()
        ).select_related('post')
    
    def lastmod(self, item):
        return item.modified_date
    
    def location(self, item):
        return item.get_absolute_url()


class BlogTagSitemap(Sitemap):
    """
    Genera un sitemap XML de todas las páginas de tags.
    Importante para facilitar indexación de taxonomía.
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
    'blog-posts-en': BlogPostEnglishSitemap,
    'blog-posts-pt': BlogPostPortugueseSitemap,
    'blog-tags': BlogTagSitemap,
}

"""Blog Web Views - Traditional HTML views with i18n support"""
from django.views.generic import ListView, DetailView
from django.http import Http404

from blog.models import Post
from blog.services import BlogService


class BlogListView(ListView):
    """Lista de posts del blog con paginación, filtro por tag y soporte i18n."""
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 9
    
    def get_queryset(self):
        """Obtiene posts publicados en el idioma activo, opcionalmente filtrados por tag."""
        tag_slug = self.request.GET.get('tag')
        return BlogService.get_published_posts(tag_slug=tag_slug)
    
    def get_context_data(self, **kwargs):
        """Agrega tags disponibles, tag activo, idioma actual, traducciones y URL canónica al contexto."""
        ctx = super().get_context_data(**kwargs)
        lang = BlogService._get_active_lang()
        ctx['tags'] = BlogService.get_all_tags()
        ctx['active_tag'] = self.request.GET.get('tag', '')
        ctx['canonical_url'] = self.request.build_absolute_uri(self.request.path)
        ctx['current_lang'] = lang
        
        # Vincular la traducción activa a cada post para renderizado directo en template
        if lang != 'es' and 'posts' in ctx:
            for post in ctx['posts']:
                post.active_translation = BlogService.get_translation(post, lang)
        
        return ctx


class BlogDetailView(DetailView):
    """Vista detalle de un post individual con resolución de idioma."""
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_field = 'slug'
    
    def get_object(self, queryset=None):
        """Obtiene el post por slug en el idioma activo e incrementa vistas."""
        slug = self.kwargs.get('slug')
        post = BlogService.get_post_by_slug(slug)
        
        if not post:
            raise Http404(f"Post con slug '{slug}' no encontrado")
        
        # Incrementar contador de vistas de forma atómica
        BlogService.increment_views(post.id)
        
        return post
    
    def get_context_data(self, **kwargs):
        """Agrega traducción activa, posts relacionados, hreflang y productos recomendados."""
        ctx = super().get_context_data(**kwargs)
        post = self.object
        lang = BlogService._get_active_lang()
        
        # Obtener la traducción activa para idiomas no-base
        translation = None
        if lang != 'es':
            translation = BlogService.get_translation(post, lang)
        
        ctx['translation'] = translation
        ctx['current_lang'] = lang
        ctx['related_posts'] = BlogService.get_related_posts(post, limit=3)
        ctx['featured_products'] = BlogService.get_featured_products(post, limit=4)
        
        # Canonical: URL del idioma actual
        if translation:
            ctx['canonical_url'] = self.request.build_absolute_uri(translation.get_absolute_url())
        else:
            ctx['canonical_url'] = self.request.build_absolute_uri(post.get_absolute_url())
        
        # Todas las traducciones disponibles para hreflang cruzado
        ctx['available_translations'] = post.translations.all()
        return ctx

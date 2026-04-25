"""Blog Web Views - Traditional HTML views"""
from django.views.generic import ListView, DetailView
from django.http import Http404
from django.core.paginator import Paginator

from blog.models import Post
from blog.services import BlogService


class BlogListView(ListView):
    """Lista de posts del blog con paginación y filtro por tag"""
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 9
    
    def get_queryset(self):
        """Obtiene posts publicados, opcionalmente filtrados por tag"""
        tag_slug = self.request.GET.get('tag')
        return BlogService.get_published_posts(tag_slug=tag_slug)
    
    def get_context_data(self, **kwargs):
        """Agrega tags disponibles y tag activo al contexto"""
        ctx = super().get_context_data(**kwargs)
        ctx['tags'] = BlogService.get_all_tags()
        ctx['active_tag'] = self.request.GET.get('tag', '')
        return ctx


class BlogDetailView(DetailView):
    """Vista detalle de un post individual"""
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_field = 'slug'
    
    def get_object(self, queryset=None):
        """Obtiene el post por slug e incrementa vistas"""
        slug = self.kwargs.get('slug')
        post = BlogService.get_post_by_slug(slug)
        
        if not post:
            raise Http404(f"Post con slug '{slug}' no encontrado")
        
        # Incrementar contador de vistas
        BlogService.increment_views(post.id)
        
        return post
    
    def get_context_data(self, **kwargs):
        """Agrega posts relacionados al contexto"""
        ctx = super().get_context_data(**kwargs)
        ctx['related_posts'] = BlogService.get_related_posts(self.object, limit=3)
        return ctx

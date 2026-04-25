"""Blog Services - Business Logic Layer"""
import logging
from typing import Optional
from datetime import datetime

from django.db.models import Q, QuerySet, F
from django.utils import timezone

from blog.models import Post, PostTag

logger = logging.getLogger(__name__)


class BlogService:
    """Servicio para la lógica de negocio del blog"""
    
    @staticmethod
    def get_published_posts(tag_slug: Optional[str] = None) -> QuerySet:
        """
        Obtiene posts publicados cuya fecha de publicación ya llegó.
        Soporta scheduling: posts con published_date en el futuro no se muestran.
        
        Args:
            tag_slug: Slug del tag para filtrar (opcional)
        
        Returns:
            QuerySet ordenado por published_date descendente
        """
        now = timezone.now()
        qs = Post.objects.filter(
            is_published=True,
            published_date__lte=now  # Solo posts cuya fecha ya llegó
        ).select_related(
            'featured_image', 'author'
        ).prefetch_related(
            'tags', 'social_metadata'
        ).order_by('-published_date')
        
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)
        
        return qs
    
    @staticmethod
    def get_post_by_slug(slug: str) -> Optional[Post]:
        """
        Obtiene un post publicado por slug (para vistas detalle).
        
        Args:
            slug: Slug del post
        
        Returns:
            Post object o None si no existe o no está publicado
        """
        try:
            return Post.objects.select_related(
                'featured_image', 'author'
            ).prefetch_related(
                'tags', 'social_metadata'
            ).get(slug=slug, is_published=True)
        except Post.DoesNotExist:
            logger.warning(f"Post no encontrado: {slug}")
            return None
    
    @staticmethod
    def get_related_posts(post: Post, limit: int = 3) -> QuerySet:
        """
        Obtiene posts relacionados basados en tags compartidos.
        
        Args:
            post: Post para el que buscar relacionados
            limit: Número máximo de posts a retornar
        
        Returns:
            QuerySet de posts relacionados (excluyendo el post actual)
        """
        tag_ids = post.tags.values_list('id', flat=True)
        
        if not tag_ids:
            # Si no tiene tags, retornar los más recientes
            return Post.objects.filter(
                is_published=True
            ).exclude(
                pk=post.pk
            ).order_by('-published_date')[:limit]
        
        # Posts con tags en común
        return Post.objects.filter(
            is_published=True,
            tags__in=tag_ids
        ).exclude(
            pk=post.pk
        ).distinct().order_by('-published_date')[:limit]
    
    @staticmethod
    def increment_views(post_id: int) -> None:
        """
        Incrementa el contador de vistas de un post.
        Usa F() para evitar race conditions.
        
        Args:
            post_id: ID del post
        """
        Post.objects.filter(pk=post_id).update(
            views_count=F('views_count') + 1
        )
    
    @staticmethod
    def search_posts(query: str) -> QuerySet:
        """
        Busca posts en título y contenido.
        
        Args:
            query: String de búsqueda
        
        Returns:
            QuerySet de posts que coinciden
        """
        return Post.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            is_published=True
        ).select_related(
            'featured_image', 'author'
        ).order_by('-published_date')
    
    @staticmethod
    def get_all_tags() -> QuerySet:
        """
        Obtiene todos los tags con posts publicados.
        
        Returns:
            QuerySet de PostTag ordenados por nombre
        """
        return PostTag.objects.filter(
            posts__is_published=True
        ).distinct().order_by('name')
    
    @staticmethod
    def get_posts_by_type(post_type: str) -> QuerySet:
        """
        Obtiene posts filtrados por tipo (article | social_repost).
        
        Args:
            post_type: Tipo de post ('article' o 'social_repost')
        
        Returns:
            QuerySet de posts del tipo especificado
        """
        return Post.objects.filter(
            is_published=True,
            post_type=post_type
        ).select_related(
            'featured_image', 'author'
        ).prefetch_related(
            'tags', 'social_metadata'
        ).order_by('-published_date')
    
    @staticmethod
    def publish_post(post_id: int, scheduled_date: Optional[datetime] = None) -> Post:
        """
        Publica un post. Si se especifica scheduled_date, programa para el futuro.
        
        Args:
            post_id: ID del post a publicar.
            scheduled_date: Fecha de publicación futura (opcional).
                            Si es None, publica ahora.
        
        Returns:
            Post actualizado.
        
        Raises:
            Post.DoesNotExist: Si el post no existe.
            ValidationError: Si el post no cumple reglas de negocio.
        """
        post = Post.objects.get(pk=post_id)
        post.is_published = True
        post.published_date = scheduled_date or timezone.now()
        post.full_clean()  # Ejecuta clean() para validar reglas de negocio
        post.save()
        logger.info(f"Post {post.id} publicado. Fecha: {post.published_date}")
        return post

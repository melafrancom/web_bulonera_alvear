"""Blog Services - Business Logic Layer"""
import logging
from typing import Optional
from datetime import datetime

from django.db.models import Q, QuerySet, F
from django.utils import timezone
from django.utils.translation import get_language

from blog.models import Post, PostTag, PostTranslation

logger = logging.getLogger(__name__)


class BlogService:
    """Servicio para la lógica de negocio del blog con soporte i18n."""
    
    @staticmethod
    def _get_active_lang() -> str:
        """Obtiene el idioma activo del request actual vía LocaleMiddleware.
        
        Qué: Retorna el código de idioma base en minúsculas (ej: 'es', 'en', 'pt').
        Por qué: Normaliza códigos regionales como 'es-ar' a 'es' para comparaciones internas consistentes.
        
        Returns:
            Código de idioma simplificado de 2 caracteres.
        """
        lang = get_language() or 'es'
        # REGLA: Normalizar 'es-ar' -> 'es' para comparaciones internas de traducción
        return lang.split('-')[0].lower()
    
    @staticmethod
    def get_published_posts(tag_slug: Optional[str] = None, lang: Optional[str] = None) -> QuerySet:
        """Obtiene posts publicados cuya fecha de publicación ya llegó.
        
        Qué: Retorna posts en el idioma activo. Para idiomas no-base (en, pt),
        solo retorna posts que tienen traducción completa registrada.
        Por qué: Evita penalización de Google por Thin Content (páginas vacías
        o duplicadas en inglés/portugués que solo muestran texto en español).
        
        Args:
            tag_slug: Slug del tag para filtrar (opcional).
            lang: Código de idioma. Si es None, usa el idioma activo del request.
        
        Returns:
            QuerySet ordenado por published_date descendente.
        """
        if lang is None:
            lang = BlogService._get_active_lang()
        
        now = timezone.now()
        qs = Post.objects.filter(
            is_published=True,
            published_date__lte=now  # Solo posts cuya fecha ya llegó
        ).select_related(
            'featured_image', 'author'
        ).prefetch_related(
            'tags', 'social_metadata', 'translations'
        ).order_by('-published_date')
        
        # REGLA: En idiomas no-base, solo listar posts con traducción completa
        if lang != 'es':
            qs = qs.filter(translations__language=lang).distinct()
        
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug).distinct()
        
        return qs
    
    @staticmethod
    def get_post_by_slug(slug: str, lang: Optional[str] = None) -> Optional[Post]:
        """Obtiene un post publicado por slug, considerando el idioma activo.
        
        Qué: Para español, busca por Post.slug directamente.
        Para en/pt, busca primero por PostTranslation.slug y retorna su post padre.
        
        Args:
            slug: Slug del post (en el idioma correspondiente).
            lang: Código de idioma. Si es None, usa el idioma activo del request.
        
        Returns:
            Post object o None si no existe, no está publicado,
            o no tiene traducción en el idioma solicitado.
        """
        if lang is None:
            lang = BlogService._get_active_lang()
        
        now = timezone.now()
        
        try:
            if lang == 'es':
                return Post.objects.select_related(
                    'featured_image', 'author'
                ).prefetch_related(
                    'tags', 'social_metadata', 'translations'
                ).get(slug=slug, is_published=True, published_date__lte=now)
            
            # Idiomas no-base: buscar por slug de traducción
            translation = PostTranslation.objects.select_related(
                'post', 'post__featured_image', 'post__author'
            ).prefetch_related(
                'post__tags', 'post__social_metadata', 'post__translations'
            ).get(
                slug=slug,
                language=lang,
                post__is_published=True,
                post__published_date__lte=now
            )
            return translation.post
        except (Post.DoesNotExist, PostTranslation.DoesNotExist):
            logger.warning(f"Post no encontrado: slug={slug}, lang={lang}")
            return None
    
    @staticmethod
    def get_translation(post: Post, lang: str) -> Optional[PostTranslation]:
        """Obtiene la traducción de un post en un idioma específico.
        
        Args:
            post: Post padre.
            lang: Código de idioma ('en' o 'pt').
        
        Returns:
            PostTranslation o None si no existe.
        """
        try:
            return post.translations.get(language=lang)
        except PostTranslation.DoesNotExist:
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

    @staticmethod
    def get_featured_products(post: Post, limit: int = 4) -> QuerySet:
        """
        Obtiene productos destacados para mostrar en el sidebar del blog.
        Estrategia: busca productos por tags del post, fallback a más vendidos.

        Args:
            post: Post actual para buscar productos relacionados.
            limit: Número máximo de productos a retornar.

        Returns:
            QuerySet de Product (de la app store).
        """
        from store.models import Product

        # Buscar por keywords del post en nombre de producto
        keywords = post.meta_keywords.split(',') if post.meta_keywords else []
        keywords = [k.strip() for k in keywords if k.strip()]

        if keywords:
            q = Q()
            for kw in keywords[:3]:  # Limitar a 3 keywords
                q |= Q(name__icontains=kw)
            products = Product.objects.filter(
                q, is_available=True
            ).order_by('-modified_date')[:limit]
            if products.exists():
                return products

        # Fallback: productos más populares
        return Product.objects.filter(
            is_available=True
        ).order_by('-modified_date')[:limit]

"""Blog API Views - DRF viewsets"""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from blog.models import Post, PostTag
from blog.services import BlogService
from blog.api.serializers import (
    PostListSerializer, PostDetailSerializer, PostTagSerializer,
    PostRelatedSerializer
)


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API read-only para posts del blog.
    Soporta búsqueda por título y filtro por tag.
    """
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['post_type', 'tags__slug']
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['published_date', 'views_count', 'created_date']
    ordering = ['-published_date']
    
    def get_queryset(self):
        """Solo retorna posts publicados"""
        return Post.objects.filter(is_published=True).select_related(
            'featured_image', 'author'
        ).prefetch_related('tags', 'social_metadata')
    
    def get_serializer_class(self):
        """Usa serializer detallado en retrieve, lightweight en list"""
        if self.action == 'retrieve':
            return PostDetailSerializer
        elif self.action == 'related':
            return PostRelatedSerializer
        return PostListSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """
        Sobreescribe retrieve para incrementar vistas al consumir el detalle.
        Mantiene el comportamiento base (retorna el objeto serializado).
        """
        instance = self.get_object()
        BlogService.increment_views(instance.id)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='related')
    def related(self, request, pk=None):
        """
        GET /api/v1/blog/posts/{id}/related/
        Retorna los posts relacionados basados en tags compartidos.
        Delega en BlogService.get_related_posts() para mantener DRY.
        """
        post = self.get_object()
        related_posts = BlogService.get_related_posts(post, limit=3)
        serializer = PostRelatedSerializer(related_posts, many=True)
        return Response(serializer.data)


class PostTagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API read-only para tags del blog.
    """
    permission_classes = [AllowAny]
    queryset = PostTag.objects.filter(posts__is_published=True).distinct()
    serializer_class = PostTagSerializer
    lookup_field = 'slug'

"""Blog API Views - DRF viewsets"""
from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from blog.models import Post, PostTag
from blog.services import BlogService
from blog.api.serializers import PostListSerializer, PostDetailSerializer, PostTagSerializer


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
        return PostListSerializer


class PostTagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API read-only para tags del blog.
    """
    permission_classes = [AllowAny]
    queryset = PostTag.objects.filter(posts__is_published=True).distinct()
    serializer_class = PostTagSerializer
    lookup_field = 'slug'

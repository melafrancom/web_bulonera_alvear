"""Category API ViewSets"""
import logging
from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from category.models import Category, SubCategory, FeaturedCategory
from category.api.serializers import (
    CategorySerializer,
    CategoryListSerializer,
    SubCategorySerializer,
    FeaturedCategorySerializer
)
from category.services import CategoryService, SubCategoryService

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para categorías.
    
    Endpoints:
    - GET /api/categories/ → Listar todas las categorías
    - GET /api/categories/{slug}/ → Detalle de categoría con subcategorías
    - GET /api/categories/featured/ → Categorías destacadas
    """
    queryset = Category.objects.all().order_by('category_name')
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        """Usa serializer diferente para list vs retrieve"""
        if self.action == 'list':
            return CategoryListSerializer
        return CategorySerializer
    
    def get_queryset(self):
        """Optimiza queries con prefetch o annotate y garantiza orden determinista"""
        if self.action == 'retrieve':
            return CategoryService.get_all_categories()
        if self.action == 'list':
            return Category.objects.annotate(_subcategory_count=Count('subcategories')).order_by('category_name')
        return Category.objects.all().order_by('category_name')
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Endpoint para obtener categorías destacadas"""
        featured = CategoryService.get_featured_categories()
        serializer = FeaturedCategorySerializer(featured, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def subcategories(self, request, slug=None):
        """Endpoint para obtener subcategorías de una categoría específica"""
        subcategories = SubCategoryService.get_subcategories_by_category(slug)
        serializer = SubCategorySerializer(subcategories, many=True)
        return Response(serializer.data)


class SubCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para subcategorías.
    
    Endpoints:
    - GET /api/subcategories/ → Listar todas las subcategorías
    - GET /api/subcategories/{slug}/ → Detalle de subcategoría
    """
    queryset = SubCategory.objects.all().order_by('subcategory_name')
    serializer_class = SubCategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Optimiza queries con select_related y orden determinista"""
        return SubCategoryService.get_all_subcategories().order_by('subcategory_name')

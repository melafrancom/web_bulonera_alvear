"""
Category App Services

Contiene la lógica de negocio para manejo de categorías y subcategorías.
"""
import logging
from typing import List, Optional
from django.db.models import QuerySet, Prefetch

from .models import Category, SubCategory, FeaturedCategory

logger = logging.getLogger(__name__)


class CategoryService:
    """Servicio para manejo de categorías"""
    
    @staticmethod
    def get_all_categories() -> QuerySet[Category]:
        """
        Obtiene todas las categorías con sus subcategorías precargadas.
        
        Returns:
            QuerySet de Category con subcategorías prefetched
        """
        return Category.objects.prefetch_related('subcategories').all()
    
    @staticmethod
    def get_category_by_slug(slug: str) -> Optional[Category]:
        """
        Obtiene una categoría por su slug con subcategorías precargadas.
        
        Args:
            slug: Slug de la categoría
            
        Returns:
            Category o None si no existe
        """
        try:
            return Category.objects.prefetch_related('subcategories').get(slug=slug)
        except Category.DoesNotExist:
            logger.warning(f"Categoría con slug '{slug}' no encontrada")
            return None
    
    @staticmethod
    def get_featured_categories() -> QuerySet[FeaturedCategory]:
        """
        Obtiene las categorías destacadas activas ordenadas por posición.
        
        Returns:
            QuerySet de FeaturedCategory activas
        """
        return FeaturedCategory.objects.filter(
            is_active=True
        ).select_related('category').order_by('position')
    
    @staticmethod
    def get_categories_for_menu() -> QuerySet[Category]:
        """
        Obtiene categorías optimizadas para el menú de navegación.
        Alias del método get_all_categories para compatibilidad con context_processor.
        
        Returns:
            QuerySet de Category con subcategorías
        """
        return CategoryService.get_all_categories()


class SubCategoryService:
    """Servicio para manejo de subcategorías"""
    
    @staticmethod
    def get_subcategory_by_slug(category_slug: str, subcategory_slug: str) -> Optional[SubCategory]:
        """
        Obtiene una subcategoría por los slugs de categoría y subcategoría.
        
        Args:
            category_slug: Slug de la categoría padre
            subcategory_slug: Slug de la subcategoría
            
        Returns:
            SubCategory o None si no existe
        """
        try:
            return SubCategory.objects.select_related('category').get(
                category__slug=category_slug,
                slug=subcategory_slug
            )
        except SubCategory.DoesNotExist:
            logger.warning(
                f"Subcategoría '{subcategory_slug}' en categoría '{category_slug}' no encontrada"
            )
            return None
    
    @staticmethod
    def get_subcategories_by_category(category_slug: str) -> QuerySet[SubCategory]:
        """
        Obtiene todas las subcategorías de una categoría específica.
        
        Args:
            category_slug: Slug de la categoría padre
            
        Returns:
            QuerySet de SubCategory
        """
        return SubCategory.objects.filter(
            category__slug=category_slug
        ).select_related('category')
    
    @staticmethod
    def get_all_subcategories() -> QuerySet[SubCategory]:
        """
        Obtiene todas las subcategorías con sus categorías precargadas.
        
        Returns:
            QuerySet de SubCategory
        """
        return SubCategory.objects.select_related('category').all()

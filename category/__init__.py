"""
Category App

App para gestión de categorías y subcategorías de productos.

Estructura:
- models.py: Modelos Category, SubCategory, FeaturedCategory
- services.py: Lógica de negocio (CategoryService, SubCategoryService)
- context_processors.py: Context processor para menú de navegación
- api/: Capa API REST (DRF) - solo lectura
- web/: Capa de vistas HTML (placeholder)
- tests/: Tests unitarios y de integración
"""

default_app_config = 'category.apps.CategoryConfig'

__all__ = []

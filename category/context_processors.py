"""
Category Context Processors

Provee datos de categorías para templates.
"""
from category.services import CategoryService


def menu_links(request):
    """
    Context processor que provee categorías para el menú de navegación.
    
    Uso en templates: {{ links }}
    """
    links = CategoryService.get_categories_for_menu()
    return dict(links=links)
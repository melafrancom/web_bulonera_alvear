"""
Category Context Processors

Provee datos de categorías para templates.
"""
from category.services import CategoryService


def menu_links(request):
    """
    Context processor que provee categorías para el menú de navegación e items de barra.
    
    Uso en templates: {{ links }} y {{ navbar_items }}
    """
    links = CategoryService.get_categories_for_menu()
    navbar_items = CategoryService.get_navbar_items()
    return dict(links=links, navbar_items=navbar_items)
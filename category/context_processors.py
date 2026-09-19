"""
Category Context Processors

Provee datos de categorías para templates con soporte de caching en Redis.
"""
from django.core.cache import cache
from category.services import CategoryService

CACHE_KEY_MENU_LINKS = 'category:menu_links'
CACHE_KEY_NAVBAR_ITEMS = 'category:navbar_items'
CACHE_TIMEOUT = 900  # 15 minutos


def menu_links(request):
    """
    Context processor que provee categorías para el menú de navegación e items de barra.
    Utiliza cache con TTL de 15 minutos para evitar consultas recurrentes a DB en cada request.
    
    Uso en templates: {{ links }} y {{ navbar_items }}
    """
    links = cache.get(CACHE_KEY_MENU_LINKS)
    if links is None:
        links = list(CategoryService.get_categories_for_menu())
        cache.set(CACHE_KEY_MENU_LINKS, links, timeout=CACHE_TIMEOUT)

    navbar_items = cache.get(CACHE_KEY_NAVBAR_ITEMS)
    if navbar_items is None:
        navbar_items = list(CategoryService.get_navbar_items())
        cache.set(CACHE_KEY_NAVBAR_ITEMS, navbar_items, timeout=CACHE_TIMEOUT)

    return dict(links=links, navbar_items=navbar_items)
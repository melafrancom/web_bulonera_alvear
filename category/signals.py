"""
Category Signals

Maneja la invalidación automática de cache ante mutaciones en categorías, subcategorías y navegación.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from category.models import Category, SubCategory, NavbarItem
from category.context_processors import CACHE_KEY_MENU_LINKS, CACHE_KEY_NAVBAR_ITEMS

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """Invalida cache de menú de navegación y navbar items cuando cambia una categoría."""
    cache.delete_many([CACHE_KEY_MENU_LINKS, CACHE_KEY_NAVBAR_ITEMS])
    logger.info("Cache de categorías y navbar invalidado por cambio en Category: %s", getattr(instance, 'slug', ''))


@receiver([post_save, post_delete], sender=SubCategory)
def invalidate_subcategory_cache(sender, instance, **kwargs):
    """Invalida cache de menú de navegación cuando cambia una subcategoría."""
    cache.delete(CACHE_KEY_MENU_LINKS)
    logger.info("Cache de menú invalidado por cambio en SubCategory: %s", getattr(instance, 'slug', ''))


@receiver([post_save, post_delete], sender=NavbarItem)
def invalidate_navbar_cache(sender, instance, **kwargs):
    """Invalida cache de navbar cuando cambia un NavbarItem."""
    cache.delete(CACHE_KEY_NAVBAR_ITEMS)
    logger.info("Cache de navbar items invalidado por cambio en NavbarItem: %s", getattr(instance, 'id', ''))

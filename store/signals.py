"""Signals de store para invalidar caché de productos relacionados."""
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from store.models import Product

_RELATION_RELEVANT_FIELDS = frozenset({
    'diameter_relation',
    'thread_formats_relation',
    'diameter',
    'thread_formats',
    'is_available',
    'stock',
})


@receiver(m2m_changed, sender=Product.related_subcategories.through)
def invalidate_related_cache_on_m2m(sender, instance, action, reverse, **kwargs):
    """Invalida la caché de recomendados cuando cambian las subcategorías relacionadas."""
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return

    from store.services import RelatedProductService

    if reverse:
        for pk in kwargs.get('pk_set') or ():
            RelatedProductService.invalidate_cache(pk)
    elif instance and instance.pk:
        RelatedProductService.invalidate_cache(instance.pk)


@receiver(post_save, sender=Product)
def invalidate_related_cache_on_product_save(sender, instance, update_fields, **kwargs):
    """Invalida la caché cuando cambian atributos de relación o disponibilidad."""
    if not instance or not instance.pk:
        return
    if update_fields is not None and not (_RELATION_RELEVANT_FIELDS & set(update_fields)):
        return

    from store.services import RelatedProductService

    RelatedProductService.invalidate_cache(instance.pk)

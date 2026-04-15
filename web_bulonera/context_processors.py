from django.conf import settings
from django.core.cache import cache
from .models import SiteTheme

def meta_settings(request):
    """
    Inyecta configuraciones globales en todos los templates.
    """
    return {
        'META_PIXEL_ENABLED': getattr(settings, 'META_PIXEL_ENABLED', False),
        'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', ''),
        'SITE_URL': getattr(settings, 'SITE_URL', ''),
        'CURRENCY': getattr(settings, 'CURRENCY', 'USD'),
        'WHATSAPP_NUMBER': getattr(settings, 'WHATSAPP_NUMBER', ''),
        'EMAIL_TO_SEND_MESSAGES': getattr(settings, 'EMAIL_TO_SEND_MESSAGES', ''),
        'DEBUG': settings.DEBUG,
    }
def site_theme(request):
    """
    Inyecta el tema activo en TODOS los templates.
    Cache de 1 hora para evitar queries constantes.
    """
    theme = cache.get('site_theme_active')
    if theme is None:
        theme = SiteTheme.objects.first()
        if theme is None:
            return {'site_theme': SiteTheme()}  # usa defaults sin guardar y sin cachear
        cache.set('site_theme_active', theme, timeout=3600)
    return {'site_theme': theme}
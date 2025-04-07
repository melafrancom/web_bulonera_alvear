# context_processors.py (crear este archivo en tu aplicación principal)

from django.conf import settings

def meta_settings(request):
    return {
        'META_PIXEL_ENABLED': getattr(settings, 'META_PIXEL_ENABLED', False),
        'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', ''),
        'SITE_URL': getattr(settings, 'SITE_URL', ''),
        'CURRENCY': getattr(settings, 'CURRENCY', 'USD'),
    }
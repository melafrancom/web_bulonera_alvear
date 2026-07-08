from django.conf import settings
from django.core.cache import cache
from .models import SiteTheme

from datetime import date, timedelta

def meta_settings(request):
    """
    Inyecta configuraciones globales en todos los templates.
    """
    # Solo inyectar rating si hay datos verificados en la cache de Redis (cero riesgo de penalización)
    google_data = cache.get('google_places_reviews_data')
    rating = google_data.get('rating') if google_data else None
    reviews_count = google_data.get('total') if google_data else None

    return {
        'META_PIXEL_ENABLED': getattr(settings, 'META_PIXEL_ENABLED', False),
        'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', ''),
        'SITE_URL': getattr(settings, 'SITE_URL', ''),
        'CURRENCY': getattr(settings, 'CURRENCY', 'USD'),
        'WHATSAPP_NUMBER': getattr(settings, 'WHATSAPP_NUMBER', ''),
        'EMAIL_TO_SEND_MESSAGES': getattr(settings, 'EMAIL_TO_SEND_MESSAGES', ''),
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL', ''),
        'INDEXNOW_API_KEY': getattr(settings, 'INDEXNOW_API_KEY', ''),
        'DEBUG': settings.DEBUG,
        'GOOGLE_MAPS_EMBED_KEY': getattr(settings, 'GOOGLE_MAPS_EMBED_KEY', ''),
        'GOOGLE_PLACE_ID': getattr(settings, 'GOOGLE_PLACE_ID', ''),
        
        # Variables dinámicas seguras
        'GOOGLE_BUSINESS_RATING': rating,
        'GOOGLE_BUSINESS_REVIEWS_COUNT': reviews_count,
        'PRICE_VALID_FROM': date.today().isoformat(),
        'PRICE_VALID_UNTIL': (date.today() + timedelta(days=30)).isoformat()
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
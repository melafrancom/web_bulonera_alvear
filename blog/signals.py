"""Blog Signals - Automatic SEO notifications"""
import logging
import requests
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.urls import reverse

from blog.models import Post

logger = logging.getLogger(__name__)

# IndexNow API endpoint
INDEXNOW_API_URL = "https://api.indexnow.org/IndexNow"


@receiver(post_save, sender=Post)
def notify_indexnow_on_post_change(sender, instance, created, **kwargs):
    """
    Notifica a IndexNow (Bing) cuando un post se publica o se modifica.
    Esto acelera la indexación de contenido nuevo.
    
    Solo notifica si:
    - El post está publicado (is_published=True)
    - Es un post nuevo o fue modificado recientemente
    - Estamos en producción (ENVIRONMENT='production')
    """
    # Solo notificar en producción
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    if environment != 'production':
        logger.debug(f"[IndexNow] Notificación omitida: ambiente {environment}")
        return
    
    # Solo notificar posts publicados
    if not instance.is_published:
        logger.debug(f"[IndexNow] Post {instance.id} no está publicado, omitiendo notificación")
        return
    
    # Construir URL absoluta del post
    try:
        # SEC-BLG-002: Usar nombre canónico de URL 'blog:post_detail'
        relative_url = reverse('blog:post_detail', kwargs={'slug': instance.slug})
        site_url = getattr(settings, 'SITE_URL', 'https://buloneraalvear.online').rstrip('/')
        post_url = f"{site_url}{relative_url}"
    except Exception as e:
        logger.error(f"[IndexNow] Error construyendo URL para post {instance.id}: {e}")
        return
    
    # Preparar payload para IndexNow
    indexnow_key = getattr(settings, 'INDEXNOW_API_KEY', None)
    if not indexnow_key:
        logger.warning("[IndexNow] INDEXNOW_API_KEY no configurado")
        return
    
    # SEC-BLG-002: Extraer host dinámicamente de SITE_URL en lugar de hardcodear
    from urllib.parse import urlparse
    parsed_site = urlparse(site_url)
    host = parsed_site.hostname or 'buloneraalvear.online'

    payload = {
        'host': host,
        'key': indexnow_key,
        'keyLocation': f"{site_url}/.well-known/IndexNow/{indexnow_key}.txt",
        'urlList': [post_url],
    }
    
    # Notificar URLs de traducciones existentes (EN, PT)
    for translation in instance.translations.all():
        try:
            tr_url = f"{site_url}{translation.get_absolute_url()}"
            payload['urlList'].append(tr_url)
        except Exception as e:
            logger.debug(f"[IndexNow] Error obteniendo URL de traducción {translation.id}: {e}")
    
    try:
        response = requests.post(
            INDEXNOW_API_URL,
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        logger.info(f"[IndexNow] ✅ Notificación enviada para {post_url} (HTTP {response.status_code})")
    except requests.exceptions.RequestException as e:
        logger.error(f"[IndexNow] ❌ Error notificando a IndexNow: {e}")
    except Exception as e:
        logger.error(f"[IndexNow] ❌ Error inesperado: {e}")


@receiver(post_delete, sender=Post)
def handle_post_deletion(sender, instance, **kwargs):
    """
    Log cuando se elimina un post (para auditoría).
    En futuras versiones, podría notificar a IndexNow para desindexación.
    """
    logger.info(f"[Blog] Post eliminado: '{instance.title}' (id={instance.id}, slug={instance.slug})")


# Nota: Las señales se registran automáticamente cuando Django importa este módulo
# desde blog/apps.py (ready() method)

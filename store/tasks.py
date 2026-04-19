import logging
from celery import shared_task
from .models import Product, CarouselImage
from .utils import ImageProcessor, CarouselImageProcessor, BannerImageProcessor, CategoryImageProcessor

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_product_image(self, product_id: int, image_path: str):
    """
    Procesa la imagen principal de un producto de manera asincrónica.
    Crea thumbnails, convierte a WebP, etc.
    """
    try:
        product = Product.objects.get(id=product_id)
        processor = ImageProcessor(image_path)
        processor.process_image()
        logger.info(f"Imagen del producto {product_id} procesada exitosamente")
        return {'status': 'success', 'product_id': product_id}
    except Product.DoesNotExist:
        logger.error(f"Producto {product_id} no encontrado")
        return {'status': 'error', 'message': 'Product not found'}
    except Exception as exc:
        logger.error(f"Error procesando imagen del producto {product_id}: {exc}")
        # Reintentar después de 60 segundos, máximo 3 intentos
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_carousel_image(self, carousel_id: int, image_path: str):
    """
    Procesa la imagen de un producto en el carrusel de manera asincrónica.
    """
    try:
        carousel = CarouselImage.objects.get(id=carousel_id)
        processor = CarouselImageProcessor(image_path)
        processor.process_image()
        logger.info(f"Imagen del carrusel {carousel_id} procesada exitosamente")
        return {'status': 'success', 'carousel_id': carousel_id}
    except CarouselImage.DoesNotExist:
        logger.error(f"Carrusel {carousel_id} no encontrado")
        return {'status': 'error', 'message': 'Carousel not found'}
    except Exception as exc:
        logger.error(f"Error procesando imagen del carrusel {carousel_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_image_asset_task(self, asset_id: int):
    """Procesa un ImageAsset centralizadamente con dispatcher por tipo."""
    from media_bank.models import ImageAsset, ImageType
    try:
        asset = ImageAsset.objects.get(id=asset_id)
        
        processor_map = {
            ImageType.PRODUCT: lambda: ImageProcessor(asset.file.path).process_image(),
            ImageType.CAROUSEL: lambda: CarouselImageProcessor(asset.file.path).process_image(),
            ImageType.BANNER: lambda: BannerImageProcessor(asset.file.path).process_image(),
            ImageType.CATEGORY: lambda: CategoryImageProcessor(asset.file.path).process_image(),
            ImageType.SUBCATEGORY: lambda: CategoryImageProcessor(asset.file.path).process_image(is_subcategory=True),
        }
        
        processor_fn = processor_map.get(asset.image_type)
        if processor_fn:
            processor_fn()
            logger.info(f"ImageAsset {asset_id} ({asset.image_type}) procesado exitosamente")
        else:
            logger.warning(f"ImageAsset {asset_id}: tipo '{asset.image_type}' sin procesador definido")
            
    except ImageAsset.DoesNotExist:
        logger.error(f"ImageAsset {asset_id} no encontrado")
    except Exception as exc:
        logger.error(f"Error procesando ImageAsset {asset_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# IndexNow Notification (FASE 1.4 — Auditoría SEO — Notificar cambios a Bing)
# ============================================================================

@shared_task(bind=True, max_retries=3)
def notify_indexnow(self, url_list: list, action: str = 'update'):
    """
    Notifica a Bing IndexNow sobre cambios de productos (nuevos, actualizados, restaurados en stock).
    
    Args:
        url_list: Lista de URLs absolutas a notificar (máx 500 por request)
        action: Tipo de acción ('create', 'update', 'restock') para logging
    
    Returns:
        dict: {'status': 'success'|'error', 'count': len(url_list), 'action': action}
    
    Raises:
        self.retry si IndexNow API devuelve error no-fatal (429, 503, etc)
    """
    import requests
    from django.conf import settings
    
    try:
        # Validar que la clave API esté configurada
        api_key = settings.INDEXNOW_API_KEY
        if not api_key:
            logger.warning("INDEXNOW_API_KEY no configurada en settings. Skipping IndexNow notification.")
            return {'status': 'skipped', 'reason': 'INDEXNOW_API_KEY not configured', 'count': 0}
        
        # Validar lista de URLs
        if not url_list or len(url_list) == 0:
            logger.warning("URL list vacía para IndexNow notification")
            return {'status': 'skipped', 'reason': 'Empty URL list', 'count': 0}
        
        # Limitar a 500 URLs por request (spec IndexNow)
        url_list = url_list[:500]
        
        # Construir payload
        payload = {
            'host': 'buloneraalvear.online',
            'key': api_key,
            'keyLocation': 'https://buloneraalvear.online/indexnow.txt',
            'urlList': url_list,
        }
        
        # POST a IndexNow API
        response = requests.post(
            'https://api.indexnow.org/indexnow',
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'},
        )
        
        # Manejo de respuestas
        if response.status_code == 200:
            logger.info(f"IndexNow notification successful: {len(url_list)} URLs [{action}]")
            return {'status': 'success', 'count': len(url_list), 'action': action}
        elif response.status_code in [429, 503]:
            # Rate limit o servicio no disponible -> retry
            logger.warning(f"IndexNow API returned {response.status_code}. Retrying...")
            raise self.retry(countdown=120, exc=Exception(f"IndexNow HTTP {response.status_code}"))
        else:
            # Otro error HTTP
            logger.error(f"IndexNow API error {response.status_code}: {response.text}")
            return {'status': 'error', 'count': len(url_list), 'action': action, 'http_status': response.status_code}
            
    except requests.RequestException as exc:
        logger.error(f"IndexNow network error: {exc}")
        raise self.retry(exc=exc, countdown=120)
    except Exception as exc:
        logger.error(f"Unexpected error in notify_indexnow: {exc}")
        raise self.retry(exc=exc, countdown=120)

import logging
from celery import shared_task
from .models import Product, CarouselImage
from .utils import ImageProcessor, CarouselImageProcessor

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

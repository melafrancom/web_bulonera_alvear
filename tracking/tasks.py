import time
import requests
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_meta_capi_event(self, event_name, event_id, user_data, custom_data):
    """
    Envía de manera asíncrona eventos a Meta Conversions API.
    Si falla por timeout o error 5xx, reintenta hasta 3 veces.
    """
    pixel_id = getattr(settings, 'META_PIXEL_ID', None)
    token = getattr(settings, 'META_CAPI_TOKEN', None)
    
    if not pixel_id or not token:
        logger.warning(f"Meta CAPI abortado: Faltan credenciales (PIXEL_ID o TOKEN) para evento {event_name}")
        return False
        
    url = f"https://graph.facebook.com/v19.0/{pixel_id}/events"
    
    payload = {
        "data": [
            {
                "event_name": event_name,
                "event_time": int(time.time()),
                "event_id": event_id,
                "action_source": "website",
                "user_data": user_data,
                "custom_data": custom_data
            }
        ],
        "access_token": token
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Meta CAPI Success: {event_name} ({event_id})")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Meta CAPI Error {event_name} ({event_id}): {str(e)}")
        # Reintentar si el error puede ser temporal
        if getattr(e.response, 'status_code', 500) >= 500 or isinstance(e, requests.exceptions.ConnectionError):
            raise self.retry(exc=e, countdown=60) # Reintenta en 60 segs
        return False

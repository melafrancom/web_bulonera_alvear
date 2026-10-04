import hashlib
import uuid
import re
from typing import Dict, Any, List, Optional
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from web_bulonera.utils import get_client_ip
from orders.models import Order
from tracking.tasks import send_meta_capi_event


class ConsentService:
    @staticmethod
    def has_advertising_consent(request) -> bool:
        """
        Lee la cookie ba_consent para determinar si el usuario autorizó cookies de publicidad.
        Formato esperado de la cookie: "a=1|d=1" o "a=0|d=0"
        """
        consent_cookie = request.COOKIES.get('ba_consent', '')
        # Extraer el flag 'd=' (advertising)
        match = re.search(r'd=(\d)', consent_cookie)
        if match:
            return match.group(1) == '1'
        return False

    @staticmethod
    def has_analytics_consent(request) -> bool:
        consent_cookie = request.COOKIES.get('ba_consent', '')
        match = re.search(r'a=(\d)', consent_cookie)
        if match:
            return match.group(1) == '1'
        return False


class TrackingPayloadService:
    @staticmethod
    def extract_user_data(request) -> Dict[str, Any]:
        """
        Extrae y hashea datos del usuario (cuando es necesario) y toma identificadores de navegador.
        Para CAPI, IPs y User Agents se envían en plano. Emails/teléfonos se deben hashear en SHA-256.
        """
        user_data = {
            "client_ip_address": get_client_ip(request),
            "client_user_agent": request.META.get('HTTP_USER_AGENT', ''),
            "fbp": request.COOKIES.get('_fbp', ''),
            "fbc": request.COOKIES.get('_fbc', ''),
        }
        
        # Limpiar vacíos
        return {k: v for k, v in user_data.items() if v}
        
    @staticmethod
    def hash_value(val: str) -> str:
        if not val:
            return ""
        return hashlib.sha256(val.strip().lower().encode('utf-8')).hexdigest()

    @staticmethod
    def build_purchase_custom_data(order: Order) -> Dict[str, Any]:
        """
        Construye el custom_data para una compra.
        OBLIGATORIO: Usar product.code (ADR-01) y convertir totales a float.
        """
        contents = []
        for item in order.orderproduct_set.all():
            contents.append({
                "id": str(item.product.code),
                "quantity": int(item.quantity),
                "item_price": float(item.purchase_price) if item.purchase_price else 0.0
            })
            
        return {
            "currency": getattr(settings, 'CURRENCY', 'ARS'),
            "value": float(order.order_total) if order.order_total else 0.0,
            "content_type": "product",
            "contents": contents
        }


class MetaCapiService:
    @staticmethod
    def enqueue_purchase(order: Order, request):
        """
        Prepara y encola un evento Purchase en Meta CAPI.
        Respeta el consentimiento y asegura idempotencia.
        """
        # 1. Chequeo de consentimiento
        if not ConsentService.has_advertising_consent(request):
            return False
            
        # 2. Generación de Event ID (estable para la misma orden)
        event_id = f"purchase.{order.order_number}"
        
        # 3. Idempotencia: Verificar si ya se envió recientemente (7 días)
        cache_key = f"capi:sent:{event_id}"
        if not cache.add(cache_key, 1, timeout=7 * 24 * 3600):
            # Ya se encoló o envió antes
            return False
            
        # 4. Construir payload
        user_data = TrackingPayloadService.extract_user_data(request)
        
        # Si la orden tiene email (ej. usuario invitado o registrado)
        if order.email:
            user_data["em"] = TrackingPayloadService.hash_value(order.email)
        if order.phone:
            # Meta espera el teléfono hasheado y preferiblemente con código de país
            phone = re.sub(r'\D', '', order.phone)
            if phone:
                user_data["ph"] = TrackingPayloadService.hash_value(phone)
        
        custom_data = TrackingPayloadService.build_purchase_custom_data(order)
        
        # 5. Encolar tarea
        send_meta_capi_event.delay('Purchase', event_id, user_data, custom_data)
        return True

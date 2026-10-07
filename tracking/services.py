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
    def normalize_phone(phone_str: str) -> str:
        """
        Normaliza teléfonos argentinos agregando el código de país (54)
        para coincidir con los perfiles de Meta y maximizar el EMQ.
        """
        if not phone_str:
            return ""
        digits = re.sub(r'\D', '', str(phone_str))
        if len(digits) == 10:
            return "54" + digits
        elif len(digits) == 11 and digits.startswith("0"):
            return "54" + digits[1:]
        return digits

    @staticmethod
    def extract_user_data(request) -> Dict[str, Any]:
        """
        Extrae y hashea datos del usuario (cuando es necesario) y toma identificadores de navegador.
        Para CAPI, IPs y User Agents se envían en plano. PII se hashea en SHA-256.
        """
        user_data = {
            "client_ip_address": get_client_ip(request),
            "client_user_agent": request.META.get('HTTP_USER_AGENT', ''),
            "fbp": request.COOKIES.get('_fbp', ''),
            "fbc": request.COOKIES.get('_fbc', ''),
        }
        
        # Mejora de EMQ (Event Match Quality) para usuarios logueados
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            if getattr(user, 'id', None):
                user_data["external_id"] = TrackingPayloadService.hash_value(str(user.id))
            if getattr(user, 'email', None):
                user_data["em"] = TrackingPayloadService.hash_value(user.email)
            
            # Soporta tanto el campo 'phone' como 'phone_number'
            phone_raw = getattr(user, 'phone', None) or getattr(user, 'phone_number', None)
            if phone_raw:
                phone_clean = TrackingPayloadService.normalize_phone(phone_raw)
                if phone_clean:
                    user_data["ph"] = TrackingPayloadService.hash_value(phone_clean)
            
            if getattr(user, 'first_name', None):
                user_data["fn"] = TrackingPayloadService.hash_value(user.first_name)
            if getattr(user, 'last_name', None):
                user_data["ln"] = TrackingPayloadService.hash_value(user.last_name)
        
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

    @staticmethod
    def build_addtocart_custom_data(product, quantity: int) -> Dict[str, Any]:
        """
        Construye el custom_data para agregar al carrito.
        OBLIGATORIO: Usar product.code (ADR-01) y floats para importes.
        """
        return {
            "currency": getattr(settings, 'CURRENCY', 'ARS'),
            "value": float(product.price * int(quantity)) if product.price else 0.0,
            "content_type": "product",
            "contents": [{
                "id": str(product.code),
                "quantity": int(quantity),
                "item_price": float(product.price) if product.price else 0.0
            }]
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
        
        # Enriquecimiento PII para maximizar el EMQ (Event Match Quality)
        if getattr(order, 'user_id', None):
            user_data["external_id"] = TrackingPayloadService.hash_value(str(order.user_id))
        elif order.email:
            # Fallback seguro: usar hash del email como external_id para invitados
            user_data["external_id"] = TrackingPayloadService.hash_value(order.email)
            
        if order.email:
            user_data["em"] = TrackingPayloadService.hash_value(order.email)
        if order.phone:
            phone_clean = TrackingPayloadService.normalize_phone(order.phone)
            if phone_clean:
                user_data["ph"] = TrackingPayloadService.hash_value(phone_clean)
                
        if getattr(order, 'first_name', None):
            user_data["fn"] = TrackingPayloadService.hash_value(order.first_name)
        if getattr(order, 'last_name', None):
            user_data["ln"] = TrackingPayloadService.hash_value(order.last_name)
        if getattr(order, 'city', None):
            user_data["ct"] = TrackingPayloadService.hash_value(order.city)
        if getattr(order, 'country', None):
            country_code = str(order.country).lower() if str(order.country) else 'ar'
            user_data["country"] = TrackingPayloadService.hash_value(country_code)
        
        custom_data = TrackingPayloadService.build_purchase_custom_data(order)
        
        # 5. Encolar tarea
        send_meta_capi_event.delay('Purchase', event_id, user_data, custom_data)
        return True

    @staticmethod
    def enqueue_add_to_cart(request, product, quantity, event_id):
        """
        Prepara y encola un evento AddToCart en Meta CAPI de forma híbrida.
        Usa el event_id provisto por JS para permitir deduplicación en el panel.
        """
        if not ConsentService.has_advertising_consent(request):
            return False
            
        # Idempotencia de 1 hora para carritos (evitar reprocesos del mismo request)
        cache_key = f"capi:sent:{event_id}"
        if not cache.add(cache_key, 1, timeout=3600):
            return False
            
        user_data = TrackingPayloadService.extract_user_data(request)
        custom_data = TrackingPayloadService.build_addtocart_custom_data(product, quantity)
        
        send_meta_capi_event.delay('AddToCart', event_id, user_data, custom_data)
        return True

    @staticmethod
    def enqueue_generate_lead(request, lead_method: str = "whatsapp", event_id: str = None, extra_user_data: dict = None):
        """
        Prepara y encola un evento Lead en Meta CAPI de forma híbrida.
        Se dispara desde vistas de redirección a WhatsApp o envíos de formulario de contacto.
        """
        if not ConsentService.has_advertising_consent(request):
            return False
            
        if not event_id:
            event_id = uuid.uuid4().hex
            
        # Idempotencia (evitar múltiples clicks rápidos del mismo usuario)
        cache_key = f"capi:sent:{event_id}"
        if not cache.add(cache_key, 1, timeout=300):
            return False
            
        user_data = TrackingPayloadService.extract_user_data(request)
        if extra_user_data:
            user_data.update(extra_user_data)
        
        # Meta recomienda incluir la fuente del lead
        custom_data = {
            "lead_event_source": lead_method,
            "currency": getattr(settings, 'CURRENCY', 'ARS'),
            "value": 0.00
        }
        
        send_meta_capi_event.delay('Lead', event_id, user_data, custom_data)
        return True

"""
ERP HTTP Client

Cliente HTTP puro para comunicación con el ERP.
Stub hasta Fase 3B - sin lógica de negocio.
"""
from typing import List, Dict, Optional
from django.conf import settings

from .exceptions import ERPUnavailableError, ERPAuthError


class ERPClient:
    """
    Cliente HTTP para el ERP.
    
    Fase 3A: Stub con NotImplementedError
    Fase 3B: Implementación real con requests + JWT
    
    NO contiene lógica de negocio - solo HTTP.
    """
    
    BASE_URL = getattr(settings, 'ERP_API_URL', None)
    
    def __init__(self, api_key: str = None):
        """
        Inicializa el cliente ERP.
        
        Args:
            api_key: API key para autenticación (opcional en Fase 3A)
        """
        self.api_key = api_key or getattr(settings, 'ERP_API_KEY', None)
        self.session = None  # requests.Session() en Fase 3B
    
    def get_products(self, **params) -> List[Dict]:
        """
        Obtiene lista de productos del ERP.
        
        Args:
            **params: Parámetros de filtrado (page, limit, category, etc.)
        
        Returns:
            Lista de productos en formato dict
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError(
            "Fase 3B: ERP API live no disponible aún. "
            "Use import_products con archivo Excel por ahora."
        )
    
    def get_product(self, code: str) -> Dict:
        """
        Obtiene un producto específico por código.
        
        Args:
            code: Código del producto
        
        Returns:
            Datos del producto
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError("Fase 3B: ERP API live no disponible aún")
    
    def get_categories(self) -> List[Dict]:
        """
        Obtiene lista de categorías del ERP.
        
        Returns:
            Lista de categorías
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError("Fase 3B: ERP API live no disponible aún")
    
    def get_stock(self, code: str) -> int:
        """
        Obtiene stock actual de un producto.
        
        Args:
            code: Código del producto
        
        Returns:
            Cantidad en stock
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError("Fase 3B: ERP API live no disponible aún")
    
    def update_stock(self, code: str, quantity: int) -> bool:
        """
        Actualiza stock de un producto en el ERP.
        
        Args:
            code: Código del producto
            quantity: Nueva cantidad
        
        Returns:
            True si se actualizó correctamente
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError("Fase 3B: ERP API live no disponible aún")
    
    def authenticate(self) -> bool:
        """
        Autentica con el ERP usando JWT.
        
        Returns:
            True si la autenticación fue exitosa
        
        Raises:
            NotImplementedError: Fase 3B no implementada aún
        """
        raise NotImplementedError("Fase 3B: ERP API live no disponible aún")
    
    def close(self):
        """Cierra la sesión HTTP"""
        if self.session:
            self.session.close()

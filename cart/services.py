"""
Cart App Services

Contiene la lógica de negocio para manejo del carrito de compras.
Elimina la duplicación de código entre usuarios autenticados y anónimos.
"""
import logging
from typing import List, Optional, Tuple, Dict
from decimal import Decimal
from django.db.models import QuerySet, Sum, F
from django.core.exceptions import ObjectDoesNotExist

from .models import Cart, CartItem
from store.models import Product, Variation
from account.models import Account

logger = logging.getLogger(__name__)


class CartService:
    """Servicio para manejo del carrito de compras"""
    
    @staticmethod
    def get_or_create_cart_id(request) -> str:
        """
        Obtiene o crea un cart_id basado en la sesión.
        
        Args:
            request: HttpRequest object
            
        Returns:
            str: cart_id de la sesión
        """
        cart_id = request.session.session_key
        if not cart_id:
            request.session.create()
            cart_id = request.session.session_key
        return cart_id
    
    @staticmethod
    def get_cart_items(request, user: Optional[Account] = None) -> QuerySet[CartItem]:
        """
        Obtiene los items del carrito según el usuario (autenticado o anónimo).
        
        Args:
            request: HttpRequest object
            user: Usuario autenticado (opcional)
            
        Returns:
            QuerySet de CartItem activos
        """
        if user and user.is_authenticated:
            return CartItem.objects.filter(
                user=user,
                is_active=True
            ).select_related('product').prefetch_related('variation')
        else:
            try:
                cart_id = CartService.get_or_create_cart_id(request)
                cart = Cart.objects.get(cart_id=cart_id)
                return CartItem.objects.filter(
                    cart=cart,
                    is_active=True
                ).select_related('product').prefetch_related('variation')
            except Cart.DoesNotExist:
                return CartItem.objects.none()
    
    @staticmethod
    def calculate_cart_totals(cart_items: QuerySet[CartItem]) -> Dict[str, any]:
        """
        Calcula los totales del carrito.
        
        Args:
            cart_items: QuerySet de CartItem
            
        Returns:
            Dict con 'total', 'quantity', 'items'
        """
        total = Decimal('0.00')
        quantity = 0
        
        for item in cart_items:
            total += Decimal(str(item.sub_total))
            quantity += item.quantity
        
        return {
            'total': total,
            'quantity': quantity,
            'items': cart_items
        }
    
    @staticmethod
    def add_to_cart(
        request,
        product: Product,
        quantity: int = 1,
        variations: List[Variation] = None,
        user: Optional[Account] = None
    ) -> CartItem:
        """
        Agrega un producto al carrito (usuarios autenticados o anónimos).
        
        Args:
            request: HttpRequest object
            product: Producto a agregar
            quantity: Cantidad a agregar
            variations: Lista de variaciones del producto
            user: Usuario autenticado (opcional)
            
        Returns:
            CartItem creado o actualizado
            
        Raises:
            ValueError: Si la cantidad es inválida
        """
        if quantity < 1:
            raise ValueError("La cantidad debe ser mayor a 0")
        
        if variations is None:
            variations = []
        
        # Determinar precio a usar
        if product.is_on_sale and product.sale_price:
            price_to_use = product.sale_price
        else:
            price_to_use = product.price
        
        # Usuario autenticado
        if user and user.is_authenticated:
            return CartService._add_to_cart_authenticated(
                user, product, quantity, variations, price_to_use
            )
        # Usuario anónimo
        else:
            return CartService._add_to_cart_anonymous(
                request, product, quantity, variations, price_to_use
            )
    
    @staticmethod
    def _add_to_cart_authenticated(
        user: Account,
        product: Product,
        quantity: int,
        variations: List[Variation],
        price: float
    ) -> CartItem:
        """Agrega producto al carrito de usuario autenticado"""
        # Buscar si ya existe un item con el mismo producto
        existing_items = CartItem.objects.filter(product=product, user=user)
        
        if existing_items.exists():
            # Verificar si existe con las mismas variaciones
            for item in existing_items:
                existing_variations = list(item.variation.all())
                if set(existing_variations) == set(variations):
                    # Actualizar cantidad del item existente
                    item.quantity += quantity
                    item.save()
                    logger.info(f"Updated cart item {item.id} for user {user.id}")
                    return item
            
            # No existe con las mismas variaciones, crear nuevo
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                user=user,
                purchase_price=price
            )
        else:
            # Crear nuevo item
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                user=user,
                purchase_price=price
            )
        
        # Agregar variaciones
        if variations:
            cart_item.variation.set(variations)
        
        logger.info(f"Created cart item {cart_item.id} for user {user.id}")
        return cart_item
    
    @staticmethod
    def _add_to_cart_anonymous(
        request,
        product: Product,
        quantity: int,
        variations: List[Variation],
        price: float
    ) -> CartItem:
        """Agrega producto al carrito de usuario anónimo"""
        cart_id = CartService.get_or_create_cart_id(request)
        
        # Obtener o crear carrito
        cart, created = Cart.objects.get_or_create(cart_id=cart_id)
        
        # Buscar si ya existe un item con el mismo producto
        existing_items = CartItem.objects.filter(product=product, cart=cart)
        
        if existing_items.exists():
            # Verificar si existe con las mismas variaciones
            for item in existing_items:
                existing_variations = list(item.variation.all())
                if set(existing_variations) == set(variations):
                    # Actualizar cantidad del item existente
                    item.quantity += quantity
                    item.save()
                    logger.info(f"Updated cart item {item.id} for cart {cart.cart_id}")
                    return item
            
            # No existe con las mismas variaciones, crear nuevo
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                cart=cart,
                purchase_price=price
            )
        else:
            # Crear nuevo item
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                cart=cart,
                purchase_price=price
            )
        
        # Agregar variaciones
        if variations:
            cart_item.variation.set(variations)
        
        logger.info(f"Created cart item {cart_item.id} for cart {cart.cart_id}")
        return cart_item
    
    @staticmethod
    def remove_from_cart(
        request,
        product_id: int,
        cart_item_id: int,
        user: Optional[Account] = None,
        remove_completely: bool = False
    ) -> bool:
        """
        Remueve o decrementa un item del carrito.
        
        Args:
            request: HttpRequest object
            product_id: ID del producto
            cart_item_id: ID del CartItem
            user: Usuario autenticado (opcional)
            remove_completely: Si True, elimina completamente; si False, decrementa
            
        Returns:
            bool: True si se removió exitosamente
        """
        try:
            if user and user.is_authenticated:
                cart_item = CartItem.objects.get(
                    product_id=product_id,
                    user=user,
                    id=cart_item_id
                )
            else:
                cart_id = CartService.get_or_create_cart_id(request)
                cart = Cart.objects.get(cart_id=cart_id)
                cart_item = CartItem.objects.get(
                    product_id=product_id,
                    cart=cart,
                    id=cart_item_id
                )
            
            if remove_completely or cart_item.quantity <= 1:
                cart_item.delete()
                logger.info(f"Deleted cart item {cart_item_id}")
            else:
                cart_item.quantity -= 1
                cart_item.save()
                logger.info(f"Decremented cart item {cart_item_id}")
            
            return True
            
        except CartItem.DoesNotExist:
            logger.warning(f"Cart item {cart_item_id} not found")
            return False
        except Cart.DoesNotExist:
            logger.warning(f"Cart not found for session")
            return False
        except Exception as e:
            logger.error(f"Error removing cart item: {e}")
            return False
    
    @staticmethod
    def get_cart_count(request, user: Optional[Account] = None) -> int:
        """
        Obtiene el conteo total de items en el carrito.
        
        Args:
            request: HttpRequest object
            user: Usuario autenticado (opcional)
            
        Returns:
            int: Cantidad total de items
        """
        cart_items = CartService.get_cart_items(request, user)
        return sum(item.quantity for item in cart_items)
    
    @staticmethod
    def merge_cart_on_login(request, user: Account) -> None:
        """
        Fusiona el carrito anónimo con el carrito del usuario al hacer login.
        
        Args:
            request: HttpRequest object
            user: Usuario que acaba de autenticarse
        """
        try:
            cart_id = CartService.get_or_create_cart_id(request)
            cart = Cart.objects.get(cart_id=cart_id)
            anonymous_items = CartItem.objects.filter(cart=cart, is_active=True)
            
            for anon_item in anonymous_items:
                # Buscar si el usuario ya tiene este producto
                user_items = CartItem.objects.filter(
                    product=anon_item.product,
                    user=user
                )
                
                anon_variations = set(anon_item.variation.all())
                merged = False
                
                for user_item in user_items:
                    user_variations = set(user_item.variation.all())
                    if anon_variations == user_variations:
                        # Fusionar cantidades
                        user_item.quantity += anon_item.quantity
                        user_item.save()
                        anon_item.delete()
                        merged = True
                        break
                
                if not merged:
                    # Transferir item al usuario
                    anon_item.user = user
                    anon_item.cart = None
                    anon_item.save()
            
            logger.info(f"Merged anonymous cart to user {user.id}")
            
        except Cart.DoesNotExist:
            logger.info(f"No anonymous cart to merge for user {user.id}")
        except Exception as e:
            logger.error(f"Error merging cart: {e}")
    
    @staticmethod
    def clear_cart(request, user: Optional[Account] = None) -> None:
        """
        Limpia todos los items del carrito.
        
        Args:
            request: HttpRequest object
            user: Usuario autenticado (opcional)
        """
        cart_items = CartService.get_cart_items(request, user)
        cart_items.delete()
        logger.info(f"Cleared cart for user {user.id if user else 'anonymous'}")

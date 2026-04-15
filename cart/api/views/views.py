"""Cart API Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from cart.models import CartItem
from cart.api.serializers import (
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer,
    CartSummarySerializer
)
from cart.services import CartService
from store.models import Product, Variation

import logging

logger = logging.getLogger(__name__)


class CartViewSet(viewsets.ViewSet):
    """
    ViewSet para manejo del carrito de compras.
    
    Endpoints:
    - GET /api/cart/ → Obtener carrito actual
    - POST /api/cart/add/ → Agregar producto al carrito
    - PATCH /api/cart/{id}/update/ → Actualizar cantidad de item
    - DELETE /api/cart/{id}/remove/ → Remover item del carrito
    - DELETE /api/cart/clear/ → Limpiar carrito completo
    - GET /api/cart/count/ → Obtener conteo de items
    """
    permission_classes = [AllowAny]
    
    def list(self, request):
        """GET /api/cart/ - Obtiene el carrito actual con todos sus items"""
        user = request.user if request.user.is_authenticated else None
        cart_items = CartService.get_cart_items(request, user)
        cart_data = CartService.calculate_cart_totals(cart_items)
        
        serializer = CartSummarySerializer({
            'items': cart_data['items'],
            'total': cart_data['total'],
            'quantity': cart_data['quantity'],
            'cart_count': cart_data['quantity']
        })
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def add(self, request):
        """POST /api/cart/add/ - Agrega un producto al carrito"""
        serializer = AddToCartSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product_id = serializer.validated_data['product_id']
            quantity = serializer.validated_data.get('quantity', 1)
            variation_ids = serializer.validated_data.get('variations', [])
            
            # Obtener producto
            product = get_object_or_404(Product, id=product_id)
            
            # Obtener variaciones si existen
            variations = []
            if variation_ids:
                variations = list(Variation.objects.filter(
                    id__in=variation_ids,
                    product=product
                ))
            
            # Agregar al carrito
            user = request.user if request.user.is_authenticated else None
            cart_item = CartService.add_to_cart(
                request=request,
                product=product,
                quantity=quantity,
                variations=variations,
                user=user
            )
            
            # Retornar item agregado
            item_serializer = CartItemSerializer(cart_item, context={'request': request})
            
            return Response({
                'status': 'success',
                'message': 'Producto agregado al carrito',
                'item': item_serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error adding to cart: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al agregar producto al carrito'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['patch'])
    def update(self, request, pk=None):
        """PATCH /api/cart/{id}/update/ - Actualiza la cantidad de un item"""
        serializer = UpdateCartItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = request.user if request.user.is_authenticated else None
            
            # Obtener el cart item
            if user:
                cart_item = get_object_or_404(CartItem, id=pk, user=user)
            else:
                cart_id = CartService.get_or_create_cart_id(request)
                cart_item = get_object_or_404(CartItem, id=pk, cart__cart_id=cart_id)
            
            # Actualizar cantidad
            cart_item.quantity = serializer.validated_data['quantity']
            cart_item.save()
            
            item_serializer = CartItemSerializer(cart_item, context={'request': request})
            
            return Response({
                'status': 'success',
                'message': 'Cantidad actualizada',
                'item': item_serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating cart item: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al actualizar item'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['delete'])
    def remove(self, request, pk=None):
        """DELETE /api/cart/{id}/remove/ - Remueve un item del carrito"""
        try:
            user = request.user if request.user.is_authenticated else None
            
            # Obtener el cart item para obtener el product_id
            if user:
                cart_item = get_object_or_404(CartItem, id=pk, user=user)
            else:
                cart_id = CartService.get_or_create_cart_id(request)
                cart_item = get_object_or_404(CartItem, id=pk, cart__cart_id=cart_id)
            
            product_id = cart_item.product_id
            
            # Remover completamente
            success = CartService.remove_from_cart(
                request=request,
                product_id=product_id,
                cart_item_id=pk,
                user=user,
                remove_completely=True
            )
            
            if success:
                return Response({
                    'status': 'success',
                    'message': 'Item removido del carrito'
                }, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({
                    'status': 'error',
                    'message': 'No se pudo remover el item'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error removing cart item: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al remover item'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """DELETE /api/cart/clear/ - Limpia todo el carrito"""
        try:
            user = request.user if request.user.is_authenticated else None
            CartService.clear_cart(request, user)
            
            return Response({
                'status': 'success',
                'message': 'Carrito limpiado'
            }, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error clearing cart: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al limpiar carrito'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def count(self, request):
        """GET /api/cart/count/ - Obtiene el conteo de items en el carrito"""
        user = request.user if request.user.is_authenticated else None
        count = CartService.get_cart_count(request, user)
        
        return Response({
            'cart_count': count
        })

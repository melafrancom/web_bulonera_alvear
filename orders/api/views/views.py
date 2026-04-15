"""Orders API Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from orders.models import Order, OrderProduct
from orders.api.serializers import (
    OrderSerializer,
    OrderListSerializer,
    CreateOrderSerializer,
    ProcessPaymentSerializer
)
from orders.services import (
    OrderService,
    PaymentService,
    CheckoutService,
    WhatsAppService
)

import logging

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para manejo de órdenes.
    
    Endpoints:
    - GET /api/orders/ → Listar órdenes del usuario
    - GET /api/orders/{id}/ → Detalle de orden
    - POST /api/orders/create/ → Crear orden desde carrito
    - POST /api/orders/{id}/process_payment/ → Procesar pago
    - GET /api/orders/{id}/whatsapp_link/ → Obtener link de WhatsApp
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_number'
    
    def get_serializer_class(self):
        """Usa serializer diferente para list vs retrieve"""
        if self.action == 'list':
            return OrderListSerializer
        return OrderSerializer
    
    def get_queryset(self):
        """Solo muestra órdenes del usuario autenticado"""
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related(
            'orderproduct_set__product',
            'orderproduct_set__variation',
            'payment'
        ).order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def create_order(self, request):
        """POST /api/orders/create/ - Crea una orden desde el carrito"""
        serializer = CreateOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener IP
            ip_address = request.META.get('REMOTE_ADDR')
            
            # Crear orden
            order = CheckoutService.complete_checkout(
                user=request.user,
                form_data=serializer.validated_data,
                ip_address=ip_address
            )
            
            # Enviar email de confirmación
            CheckoutService.send_order_confirmation_email(order)
            
            # Retornar orden creada
            order_serializer = OrderSerializer(order, context={'request': request})
            
            return Response({
                'status': 'success',
                'message': 'Orden creada exitosamente',
                'order': order_serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating order for user {request.user.id}: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al crear la orden'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def process_payment(self, request, order_number=None):
        """POST /api/orders/{order_number}/process_payment/ - Procesa el pago de una orden"""
        serializer = ProcessPaymentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Obtener orden
            order = get_object_or_404(
                Order,
                order_number=order_number,
                user=request.user,
                is_ordered=False
            )
            
            # Procesar pago
            payment_data = {
                'payment_id': serializer.validated_data['payment_id'],
                'payment_method': serializer.validated_data['payment_method'],
                'status': serializer.validated_data['status']
            }
            
            payment = PaymentService.process_payment(
                user=request.user,
                order=order,
                payment_data=payment_data
            )
            
            # Enviar email de confirmación
            CheckoutService.send_order_confirmation_email(order)
            
            # Retornar orden actualizada
            order_serializer = OrderSerializer(order, context={'request': request})
            
            return Response({
                'status': 'success',
                'message': 'Pago procesado exitosamente',
                'order': order_serializer.data,
                'payment_id': payment.payment_id
            })
            
        except ValueError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error processing payment for order {order_number}: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al procesar el pago'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def whatsapp_link(self, request, order_number=None):
        """GET /api/orders/{order_number}/whatsapp_link/ - Obtiene link de WhatsApp"""
        try:
            # Obtener orden
            order = get_object_or_404(
                Order,
                order_number=order_number,
                user=request.user
            )
            
            # Generar link
            whatsapp_link = WhatsAppService.generate_whatsapp_link(order)
            
            return Response({
                'status': 'success',
                'whatsapp_link': whatsapp_link,
                'order_number': order.order_number
            })
            
        except Exception as e:
            logger.error(f"Error generating WhatsApp link for order {order_number}: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al generar link de WhatsApp'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def process_whatsapp(self, request, order_number=None):
        """POST /api/orders/{order_number}/process_whatsapp/ - Procesa orden para WhatsApp"""
        try:
            # Obtener orden
            order = get_object_or_404(
                Order,
                order_number=order_number,
                user=request.user,
                is_ordered=False
            )
            
            # Procesar para WhatsApp
            payment, whatsapp_link = WhatsAppService.process_whatsapp_order(order)
            
            # Enviar email de confirmación
            CheckoutService.send_order_confirmation_email(order)
            
            return Response({
                'status': 'success',
                'message': 'Orden procesada para WhatsApp',
                'whatsapp_link': whatsapp_link,
                'order_number': order.order_number,
                'payment_id': payment.payment_id
            })
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp order {order_number}: {e}")
            return Response({
                'status': 'error',
                'message': 'Error al procesar orden para WhatsApp'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

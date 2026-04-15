"""Contact API ViewSets"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from contact.models import ContactOption
from contact.api.serializers import ContactOptionSerializer
from contact.services import ContactService

import logging

logger = logging.getLogger(__name__)


class ContactOptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para crear y recuperar mensajes de contacto.
    
    Permite:
    - POST /api/contact/ → Crear nuevo contacto
    - GET /api/contact/ → Listar contactos (admin only)
    """
    queryset = ContactOption.objects.all()
    serializer_class = ContactOptionSerializer
    permission_classes = [AllowAny]  # POST desde formulario público, GET requiere permisos
    
    def create(self, request, *args, **kwargs):
        """Crea un nuevo contacto usando el servicio"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            contact = ContactService.create_contact(
                name=serializer.validated_data.get('name'),
                email=serializer.validated_data.get('email'),
                contact_method=serializer.validated_data.get('contact_method', 'email'),
                subject=serializer.validated_data.get('subject'),
                message=serializer.validated_data.get('message')
            )
            
            output_serializer = self.get_serializer(contact)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creando contacto vía API: {e}")
            return Response(
                {'error': 'Error procesando el formulario de contacto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_queryset(self):
        """Solo admin puede ver todos los contactos"""
        if self.request.user.is_staff:
            return self.queryset
        return ContactOption.objects.none()

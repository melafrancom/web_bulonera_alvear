"""Contact API ViewSets"""
import logging
from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle

from contact.models import ContactOption
from contact.api.serializers import ContactOptionSerializer
from contact.services import ContactService

logger = logging.getLogger(__name__)


class ContactOptionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet para crear y consultar mensajes de contacto.

    Endpoints:
    - POST /api/v1/contact/contact/      → Crear contacto (Público, Rate Limited con scope 'contact')
    - GET  /api/v1/contact/contact/      → Listar contactos (Solo Admin / Staff)
    - GET  /api/v1/contact/contact/{id}/ → Ver detalle de contacto (Solo Admin / Staff)
    - PUT, PATCH, DELETE están bloqueados (405 Method Not Allowed)
    """
    queryset = ContactOption.objects.all().order_by('-created_at')
    serializer_class = ContactOptionSerializer

    def get_permissions(self):
        """
        Permisos granulares:
        - create: AllowAny (formulario público)
        - list, retrieve: IsAdminUser (solo personal autorizado)
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAdminUser()]

    def get_throttles(self):
        """
        Aplica throttle ScopedRateThrottle para la acción 'create' (scope 'contact').
        """
        if self.action == 'create':
            self.throttle_scope = 'contact'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        """Crea un nuevo contacto a través de la capa de servicio ContactService"""
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
        except Exception:
            logger.error("Error no controlado creando contacto vía API", exc_info=True)
            return Response(
                {'error': 'Error procesando el formulario de contacto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

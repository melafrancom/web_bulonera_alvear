"""Account API Views"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from account.models import Account, UserProfile
from account.api.serializers import (
    AccountDetailSerializer, RegistrationSerializer, 
    LoginSerializer, PasswordChangeSerializer
)
from account.services import (
    AccountRegistrationService, AccountLoginService, 
    PasswordResetService, ProfileUpdateService
)
import logging

logger = logging.getLogger(__name__)


class RegistrationAPIView(viewsets.ViewSet):
    """Endpoint para registro de nuevos usuarios"""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """POST /api/auth/register/"""
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = AccountRegistrationService.register(
                    first_name=serializer.validated_data['first_name'],
                    last_name=serializer.validated_data['last_name'],
                    email=serializer.validated_data['email'],
                    phone=request.data.get('phone', ''),
                    password=serializer.validated_data['password'],
                    request=request
                )
                return Response({
                    'message': 'Registro exitoso. Verifica tu email.',
                    'user_id': user.id
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error registrando usuario: {e}")
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPIView(viewsets.ViewSet):
    """Endpoint para acceder al perfil del usuario autenticado"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /api/account/me/"""
        try:
            serializer = AccountDetailSerializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        """PUT /api/account/update/"""
        try:
            ProfileUpdateService.update_user_profile(
                user=request.user,
                first_name=request.data.get('first_name'),
                last_name=request.data.get('last_name'),
                phone=request.data.get('phone')
            )
            serializer = AccountDetailSerializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error actualizando perfil: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

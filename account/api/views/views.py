"""Account API Views"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import login as django_login, logout as django_logout
import logging

from account.models import Account, UserProfile
from account.api.serializers import (
    AccountDetailSerializer, RegistrationSerializer, 
    LoginSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    UpdateProfileSerializer, UpdateProfileAddressSerializer,
    DashboardSerializer
)
from account.services import (
    AccountRegistrationService, AccountLoginService, 
    PasswordResetService, ProfileUpdateService,
    AccountActivationService, PasswordChangeService,
    DashboardService
)

logger = logging.getLogger(__name__)


class AuthViewSet(viewsets.ViewSet):
    """ViewSet para autenticación (registro, login, logout)"""
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """POST /api/account/auth/register/"""
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = AccountRegistrationService.register(
                    first_name=serializer.validated_data['first_name'],
                    last_name=serializer.validated_data['last_name'],
                    email=serializer.validated_data['email'],
                    phone=serializer.validated_data.get('phone', ''),
                    password=serializer.validated_data['password'],
                    request=request
                )
                return Response({
                    'message': 'Registro exitoso. Verifica tu email para activar tu cuenta.',
                    'user_id': user.id,
                    'email': user.email
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error registrando usuario: {e}")
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """POST /api/account/auth/login/"""
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = AccountLoginService.authenticate_user(email, password)
            if user is not None:
                django_login(request, user)
                
                # Crear o obtener token para API
                token, created = Token.objects.get_or_create(user=user)
                
                account_data = AccountDetailSerializer(user).data
                return Response({
                    'message': 'Login exitoso',
                    'token': token.key,
                    'user': account_data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Credenciales inválidas'
                }, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """POST /api/account/auth/logout/"""
        # Eliminar token si existe
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        
        django_logout(request)
        return Response({'message': 'Logout exitoso'}, status=status.HTTP_200_OK)


class ProfileViewSet(viewsets.ViewSet):
    """ViewSet para gestión de perfil de usuario"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """GET /api/account/profile/me/"""
        try:
            serializer = AccountDetailSerializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error obteniendo perfil: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """PUT/PATCH /api/v1/account/profile/update_profile/"""
        serializer = UpdateProfileSerializer(data=request.data)
        if serializer.is_valid():
            try:
                ProfileUpdateService.update_user_profile(
                    user=request.user,
                    first_name=serializer.validated_data.get('first_name'),
                    last_name=serializer.validated_data.get('last_name'),
                    phone=serializer.validated_data.get('phone')
                )
                account_data = AccountDetailSerializer(request.user).data
                return Response({
                    'message': 'Perfil actualizado exitosamente',
                    'user': account_data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error actualizando perfil: {e}")
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_address(self, request):
        """PUT/PATCH /api/account/profile/update_address/"""
        serializer = UpdateProfileAddressSerializer(data=request.data)
        if serializer.is_valid():
            try:
                ProfileUpdateService.update_user_profile_address(
                    user=request.user,
                    address_line_1=serializer.validated_data.get('address_line_1'),
                    address_line_2=serializer.validated_data.get('address_line_2'),
                    city=serializer.validated_data.get('city'),
                    state=serializer.validated_data.get('state'),
                    country=serializer.validated_data.get('country')
                )
                account_data = AccountDetailSerializer(request.user).data
                return Response({
                    'message': 'Dirección actualizada exitosamente',
                    'user': account_data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error actualizando dirección: {e}")
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """POST /api/account/profile/change_password/"""
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            try:
                success = PasswordChangeService.change_password(
                    user=request.user,
                    current_password=serializer.validated_data['current_password'],
                    new_password=serializer.validated_data['new_password']
                )
                if success:
                    return Response({
                        'message': 'Contraseña actualizada exitosamente'
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'error': 'Contraseña actual incorrecta'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Error cambiando contraseña: {e}")
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """GET /api/account/profile/dashboard/"""
        try:
            dashboard_data = DashboardService.get_user_dashboard_data(request.user)
            serializer = DashboardSerializer(dashboard_data)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error obteniendo dashboard: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetViewSet(viewsets.ViewSet):
    """ViewSet para recuperación de contraseña"""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def request_reset(self, request):
        """POST /api/account/password/request_reset/"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            success = PasswordResetService.send_reset_email(email, request)
            if success:
                return Response({
                    'message': 'Email de recuperación enviado'
                }, status=status.HTTP_200_OK)
            else:
                # Por seguridad, no revelamos si el email existe o no
                return Response({
                    'message': 'Si el email existe, recibirás instrucciones'
                }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='confirm/(?P<uidb64>[^/.]+)/(?P<token>[^/.]+)')
    def confirm_reset(self, request, uidb64=None, token=None):
        """POST /api/account/password/confirm/{uidb64}/{token}/"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = PasswordResetService.validate_reset_token(uidb64, token)
            if user:
                success = PasswordResetService.reset_password(
                    uid=str(user.pk),
                    new_password=serializer.validated_data['password']
                )
                if success:
                    return Response({
                        'message': 'Contraseña actualizada exitosamente'
                    }, status=status.HTTP_200_OK)
            
            return Response({
                'error': 'Token inválido o expirado'
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


__all__ = ['AuthViewSet', 'ProfileViewSet', 'PasswordResetViewSet']

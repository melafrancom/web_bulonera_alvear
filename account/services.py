"""
Account App Services

Contiene la lógica de negocio pura para gestión de autenticación y perfiles de usuario.
"""
import logging
from django.contrib.auth import authenticate
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
from django.conf import settings

from account.models import Account, UserProfile

logger = logging.getLogger(__name__)


class AccountRegistrationService:
    """Servicio para registro de nuevos usuarios"""
    
    @staticmethod
    def register(first_name: str, last_name: str, email: str, phone: str, password: str, request) -> Account:
        """Crear nuevo usuario y enviar email de verificación"""
        username = email.split('@')[0]
        
        user = Account.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            username=username,
            password=password
        )
        user.phone = phone
        user.save()
        
        # Crear perfil de usuario
        profile = UserProfile.objects.create(
            user=user,
            profile_picture='default/default-user.png'
        )
        
        # Enviar email de verificación
        AccountRegistrationService.send_verification_email(user, request)
        logger.info(f"Usuario registrado: {email}")
        
        return user
    
    @staticmethod
    def send_verification_email(user: Account, request) -> bool:
        """Envía email de activación a nuevo usuario"""
        try:
            current_site = get_current_site(request)
            mail_subject = 'Activa tu cuenta en Bulonera Alvear para continuar'
            body = render_to_string('account/account_verification_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            
            email = EmailMessage(mail_subject, body, to=[user.email])
            email.send(fail_silently=False)
            logger.info(f"Email de verificación enviado a {user.email}")
            return True
        except Exception as e:
            logger.error(f"Error enviando email de verificación a {user.email}: {e}")
            return False


class AccountLoginService:
    """Servicio para gestión de login"""
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Account | None:
        """Autentica usuario con email y password"""
        try:
            user = authenticate(email=email, password=password)
            if user is not None:
                logger.info(f"Usuario autenticado: {email}")
            else:
                logger.warning(f"Intento fallido de login para: {email}")
            return user
        except Exception as e:
            logger.error(f"Error autenticando usuario {email}: {e}")
            return None


class PasswordResetService:
    """Servicio para recuperación de contraseña"""
    
    @staticmethod
    def send_reset_email(email: str, request) -> bool:
        """Envía email para recuperar contraseña"""
        try:
            user = Account.objects.get(email=email)
            
            current_site = get_current_site(request)
            mail_subject = 'Recupera tu Contraseña'
            body = render_to_string('account/reset_password_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            
            email_msg = EmailMessage(mail_subject, body, to=[user.email])
            email_msg.send(fail_silently=False)
            logger.info(f"Email de reset enviado a {user.email}")
            return True
            
        except Account.DoesNotExist:
            logger.warning(f"Intento de reset para email inexistente: {email}")
            return False
        except Exception as e:
            logger.error(f"Error enviando reset email a {email}: {e}")
            return False
    
    @staticmethod
    def validate_reset_token(uidb64: str, token: str) -> Account | None:
        """Valida si el token de reset es correcto"""
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Account._default_manager.get(pk=uid)
            
            if default_token_generator.check_token(user, token):
                logger.info(f"Token de reset validado para {user.email}")
                return user
            else:
                logger.warning(f"Token inválido para usuario {uid}")
                return None
                
        except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
            logger.warning(f"Error descodificando token reset")
            return None
    
    @staticmethod
    def reset_password(uid: str, new_password: str) -> bool:
        """Actualiza la contraseña del usuario"""
        try:
            user = Account.objects.get(pk=uid)
            user.set_password(new_password)
            user.save()
            logger.info(f"Contraseña actualizada para usuario {user.email}")
            return True
        except Account.DoesNotExist:
            logger.error(f"Usuario con uid {uid} no encontrado para reset de password")
            return False
        except Exception as e:
            logger.error(f"Error actualizando password: {e}")
            return False


class ProfileUpdateService:
    """Servicio para actualización de perfil"""
    
    @staticmethod
    def update_user_profile(user: Account, first_name: str = None, last_name: str = None, 
                           phone: str = None, email: str = None) -> bool:
        """Actualiza datos del usuario"""
        try:
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            if phone:
                user.phone = phone
            if email:
                user.email = email
                user.username = email.split('@')[0]
            
            user.save()
            logger.info(f"Perfil actualizado para usuario {user.email}")
            return True
        except Exception as e:
            logger.error(f"Error actualizando perfil de {user.email}: {e}")
            return False
    
    @staticmethod
    def update_user_profile_picture(user: Account, profile_picture) -> bool:
        """Actualiza foto de perfil"""
        try:
            if not hasattr(user, 'userprofile'):
                UserProfile.objects.create(user=user)
            
            user.userprofile.profile_picture = profile_picture
            user.userprofile.save()
            logger.info(f"Foto de perfil actualizada para {user.email}")
            return True
        except Exception as e:
            logger.error(f"Error actualizando foto de perfil de {user.email}: {e}")
            return False

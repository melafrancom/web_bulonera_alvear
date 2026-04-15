"""Account API Serializers"""
from rest_framework import serializers
from account.models import Account, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer para perfil de usuario"""
    profile_picture_url = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'address_line_1', 'address_line_2', 'city', 'state', 
            'country', 'profile_picture', 'profile_picture_url', 'full_address'
        ]
        read_only_fields = ['profile_picture_url', 'full_address']
    
    def get_profile_picture_url(self, obj):
        return obj.get_profile_picture_url()
    
    def get_full_address(self, obj):
        return obj.full_address()


class AccountSerializer(serializers.ModelSerializer):
    """Serializer básico de cuenta"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'phone', 'full_name']
        read_only_fields = ['id', 'email', 'username']
    
    def get_full_name(self, obj):
        return obj.full_name()


class AccountDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado de cuenta con perfil"""
    userprofile = UserProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 
            'phone', 'full_name', 'date_joined', 'last_login', 
            'is_active', 'userprofile'
        ]
        read_only_fields = ['id', 'email', 'username', 'date_joined', 'last_login', 'is_active']
    
    def get_full_name(self, obj):
        return obj.full_name()


class RegistrationSerializer(serializers.Serializer):
    """Serializer para registro de nuevos usuarios"""
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=35)
    last_name = serializers.CharField(max_length=55)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden"})
        
        if Account.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "Este email ya está registrado"})
        
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer para login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña (usuario autenticado)"""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden"})
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer para solicitar reset de contraseña"""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer para confirmar reset de contraseña"""
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden"})
        return data


class UpdateProfileSerializer(serializers.Serializer):
    """Serializer para actualizar perfil"""
    first_name = serializers.CharField(max_length=35, required=False)
    last_name = serializers.CharField(max_length=55, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class UpdateProfileAddressSerializer(serializers.Serializer):
    """Serializer para actualizar dirección"""
    address_line_1 = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=50, required=False, allow_blank=True)
    state = serializers.CharField(max_length=50, required=False, allow_blank=True)
    country = serializers.CharField(max_length=50, required=False, allow_blank=True)


class DashboardSerializer(serializers.Serializer):
    """Serializer para datos del dashboard"""
    orders_count = serializers.IntegerField()
    new_orders_count = serializers.IntegerField()
    accepted_orders_count = serializers.IntegerField()
    completed_orders_count = serializers.IntegerField()
    cancelled_orders_count = serializers.IntegerField()


__all__ = [
    'UserProfileSerializer',
    'AccountSerializer',
    'AccountDetailSerializer',
    'RegistrationSerializer',
    'LoginSerializer',
    'PasswordChangeSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetConfirmSerializer',
    'UpdateProfileSerializer',
    'UpdateProfileAddressSerializer',
    'DashboardSerializer',
]

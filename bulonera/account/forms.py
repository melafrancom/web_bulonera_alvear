from typing import Any, Mapping
from django import forms
from django.core.files.base import File
from django.db.models.base import Model
from django.forms.utils import ErrorList

# LOCAL APPS:
from .models import Account, UserProfile  

#Debemos crear los formularios a utilizar: Formularios de registros, de usuario, y de perfil del usuario.
class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Ingrese Contraseña',
        'class': 'form-control',
    }))
    
    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'phone', 'email', 'password']
        
    
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs['placeholder'] = 'Ingrese su nombre'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Ingrese su apellido'
        self.fields['phone'].widget.attrs['placeholder'] = 'Ingrese su numero de telefono'
        self.fields['email'].widget.attrs['placeholder'] = 'Ingrese su email'
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
            
    def clean(self):
        cleaned_data = super(RegistrationForm, self).clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password != confirm_password:
            raise forms.ValidationError(
                'Parece que la contraseña no coincide, verifique su información.'
            )
    

class UserForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'phone']
        
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

class UserProfileForm(forms.ModelForm):
    profile_picture = forms.ImageField(required=False, error_messages = {'invalid': ('Solo archivos de imagen')}, widget=forms.FileInput)
    class Meta:
        model = UserProfile
        fields = ['address_line_1', 'address_line_2', 'city', 'state', 'country', 'profile_picture']
        
    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
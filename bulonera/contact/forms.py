from django import forms
from .models import ContactOption

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactOption
        fields = ['name', 'email', 'contact_method', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tu@email.com'}),
            'contact_method': forms.Select(attrs={'class': 'form-control', 'id': 'contact-method'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Tu mensaje', 'rows': 5, 'id': 'message-field'}),
        }
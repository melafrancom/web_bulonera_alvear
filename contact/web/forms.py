from django import forms
from contact.models import ContactOption


class ContactForm(forms.ModelForm):
    # Honeypot anti-spam: invisible para humanos, bots lo rellenan automáticamente
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
        }),
        label=''
    )

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

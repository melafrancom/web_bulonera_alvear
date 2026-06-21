from django.contrib import admin
from django import forms
from django.contrib import messages
from .models import SiteTheme

class SiteThemeForm(forms.ModelForm):
    class Meta:
        model = SiteTheme
        fields = '__all__'
        widgets = {
            'primary_50': forms.TextInput(attrs={'type': 'color'}),
            'primary_100': forms.TextInput(attrs={'type': 'color'}),
            'primary_200': forms.TextInput(attrs={'type': 'color'}),
            'primary_300': forms.TextInput(attrs={'type': 'color'}),
            'primary_400': forms.TextInput(attrs={'type': 'color'}),
            'primary_500': forms.TextInput(attrs={'type': 'color'}),
            'primary_600': forms.TextInput(attrs={'type': 'color'}),
            'primary_700': forms.TextInput(attrs={'type': 'color'}),
            'primary_800': forms.TextInput(attrs={'type': 'color'}),
            'primary_900': forms.TextInput(attrs={'type': 'color'}),
            'accent_400': forms.TextInput(attrs={'type': 'color'}),
            'accent_500': forms.TextInput(attrs={'type': 'color'}),
            'accent_600': forms.TextInput(attrs={'type': 'color'}),
            'soft_bg': forms.TextInput(attrs={'type': 'color'}),
            'navbar_bg': forms.TextInput(attrs={'type': 'color'}),
            'navbar_text': forms.TextInput(attrs={'type': 'color'}),
            'topbar_text': forms.TextInput(attrs={'type': 'color'}),
            'subbar_from': forms.TextInput(attrs={'type': 'color'}),
            'subbar_to': forms.TextInput(attrs={'type': 'color'}),
            'footer_bg': forms.TextInput(attrs={'type': 'color'}),
            'footer_text': forms.TextInput(attrs={'type': 'color'}),
            'quickcat_bg': forms.TextInput(attrs={'type': 'color'}),
            'bestseller_bg': forms.TextInput(attrs={'type': 'color'}),
            'navbar_opacity': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100'}),
            'subbar_opacity': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100'}),
            'footer_opacity': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100'}),
            'quickcat_opacity': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100'}),
            'bestseller_opacity': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100'}),
        }

@admin.register(SiteTheme)
class SiteThemeAdmin(admin.ModelAdmin):
    form = SiteThemeForm
    
    fieldsets = (
        ('Configuración General', {
            'fields': ('name',)
        }),
        ('🔵 Color Primario', {
            'description': 'Usado en botones, navbar, links activos, gradientes del carrusel.',
            'fields': (
                ('primary_600', 'primary_700'),
                ('primary_800', 'primary_900'),
                ('primary_50', 'primary_100', 'primary_200'),
                ('primary_300', 'primary_400', 'primary_500'),
            ),
        }),
        ('🟡 Color Acento', {
            'description': 'Usado en estrellas de rating y badges de oferta.',
            'fields': (('accent_400', 'accent_500', 'accent_600'),),
        }),
        ('🏗️ Estructura del Sitio', {
            'description': 'Colores y opacidad del Navbar, barra de título y Footer. El modo oscuro tiene sus propios colores y no se ve afectado.',
            'fields': (
                ('navbar_bg', 'navbar_opacity', 'navbar_text'),
                ('topbar_text'),
                ('subbar_from', 'subbar_to', 'subbar_opacity'),
                ('footer_bg', 'footer_opacity', 'footer_text'),
            ),
        }),
        ('🏠 Secciones del Home', {
            'description': 'Personalización de secciones específicas de la página de inicio.',
            'fields': (
                ('quickcat_bg', 'quickcat_opacity'),
                ('bestseller_bg', 'bestseller_opacity'),
            ),
        }),
        ('🎨 Fondos', {
            'fields': ('soft_bg',),
        }),
    )

    def has_add_permission(self, request):
        """Previene que se agreguen múltiples temas, ya que es Singleton."""
        if SiteTheme.objects.exists():
            return False
        return super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        messages.success(request, "✅ Tema guardado. Los cambios se aplican de inmediato.")

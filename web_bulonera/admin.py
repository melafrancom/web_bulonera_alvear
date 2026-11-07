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


from django.core.cache import cache
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from .models import BusinessHoursSetting, BusinessHoursPeriod, BusinessHoursException
from .business_hours import get_business_hours_data


class BusinessHoursPeriodInlineFormSet(BaseInlineFormSet):
    """
    Valida coherencia en los períodos semanales:
    # REGLA: Exige al menos un período activo y previene solapamientos en un mismo día.
    """
    def clean(self):
        super().clean()
        active_periods = []
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or self._should_delete_form(form):
                continue
            cleaned = form.cleaned_data
            day = cleaned.get('day')
            op = cleaned.get('opening_time')
            cl = cleaned.get('closing_time')
            if day and op and cl:
                active_periods.append((day, op, cl))

        if not active_periods:
            raise ValidationError("Debe configurar al menos un período de atención semanal.")

        periods_by_day = {}
        for day, op, cl in active_periods:
            periods_by_day.setdefault(day, []).append((op, cl))

        day_names = dict(BusinessHoursPeriod.DAYS_OF_WEEK)
        for day, intervals in periods_by_day.items():
            sorted_intervals = sorted(intervals, key=lambda x: x[0])
            for i in range(len(sorted_intervals) - 1):
                curr_op, curr_cl = sorted_intervals[i]
                next_op, next_cl = sorted_intervals[i + 1]
                if curr_cl > next_op:
                    raise ValidationError(
                        f"Solapamiento horario en {day_names.get(day, f'Día {day}')}: "
                        f"el período {curr_op.strftime('%H:%M')}–{curr_cl.strftime('%H:%M')} "
                        f"se superpone con {next_op.strftime('%H:%M')}–{next_cl.strftime('%H:%M')}."
                    )


class BusinessHoursExceptionInlineFormSet(BaseInlineFormSet):
    """
    Valida excepciones / feriados:
    # REGLA: Previene conflictos de cierre total y horas parciales para una misma fecha.
    """
    def clean(self):
        super().clean()
        active_exceptions = []
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or self._should_delete_form(form):
                continue
            cleaned = form.cleaned_data
            date_val = cleaned.get('date')
            is_closed = cleaned.get('is_closed')
            op = cleaned.get('opening_time')
            cl = cleaned.get('closing_time')
            if date_val:
                active_exceptions.append((date_val, is_closed, op, cl))

        by_date = {}
        for d, closed, op, cl in active_exceptions:
            by_date.setdefault(d, []).append((closed, op, cl))

        for d, rows in by_date.items():
            if len(rows) > 1:
                has_closed = any(r[0] for r in rows)
                if has_closed:
                    raise ValidationError(
                        f"Conflicto en la fecha {d.strftime('%d/%m/%Y')}: no puede marcarse 'Cerrado todo el día' y simultáneamente definir horas especiales."
                    )
                sorted_special = sorted([(r[1], r[2]) for r in rows if r[1] and r[2]], key=lambda x: x[0])
                for i in range(len(sorted_special) - 1):
                    if sorted_special[i][1] > sorted_special[i + 1][0]:
                        raise ValidationError(
                            f"Solapamiento horario en fecha especial {d.strftime('%d/%m/%Y')}."
                        )


class BusinessHoursPeriodInline(admin.TabularInline):
    model = BusinessHoursPeriod
    formset = BusinessHoursPeriodInlineFormSet
    extra = 1
    fields = ('day', 'opening_time', 'closing_time')
    ordering = ('day', 'opening_time')


class BusinessHoursExceptionInline(admin.TabularInline):
    model = BusinessHoursException
    formset = BusinessHoursExceptionInlineFormSet
    extra = 0
    fields = ('date', 'reason', 'is_closed', 'opening_time', 'closing_time')
    ordering = ('date',)


@admin.register(BusinessHoursSetting)
class BusinessHoursSettingAdmin(admin.ModelAdmin):
    """
    Administración centralizada de horarios comerciales (Fuente única de la web).
    # REGLA: Invalida y refresca la caché para actualización inmediata sin redeploy.
    """
    inlines = [BusinessHoursPeriodInline, BusinessHoursExceptionInline]
    fieldsets = (
        ('Información General', {
            'description': 'Configuración horaria semanal única para la web, Google Schema.org y metadatos.',
            'fields': ('name', 'holiday_note')
        }),
    )

    def changelist_view(self, request, extra_context=None):
        """
        Redirección 1-clic al Singleton:
        Al ingresar a 'Horario Comercial' desde el menú de Django Admin,
        accede directamente a la pantalla de edición del horario único.
        """
        instance = BusinessHoursSetting.load()
        return redirect(reverse('admin:web_bulonera_businesshourssetting_change', args=[instance.pk]))

    def has_add_permission(self, request):
        if BusinessHoursSetting.objects.exists():
            return False
        return super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete('business_hours_active')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        cache.delete('business_hours_active')
        get_business_hours_data()
        messages.success(
            request,
            "✅ Horarios comerciales guardados. Los cambios se reflejan en toda la web y Schema.org de inmediato."
        )

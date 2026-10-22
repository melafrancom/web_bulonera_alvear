from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from .models import Order, Payment, OrderProduct, OrderRevocation
from .services import RevocationService


class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = ('payment', 'user', 'product', 'quantity', 'purchase_price', 'ordered')
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number',
        'full_name',
        'delivery_badge',
        'invoice_badge',
        'phone',
        'email',
        'order_total',
        'status',
        'is_ordered',
        'created_at',
    ]
    list_filter = ['delivery_type', 'invoice_type', 'status', 'is_ordered', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email', 'doc_number', 'business_name']
    list_per_page = 20
    inlines = [OrderProductInline]

    @admin.display(description='Entrega')
    def delivery_badge(self, obj):
        colors = {
            'pickup': '#059669',      # emerald
            'shipping': '#2563eb',    # blue
            'unspecified': '#6b7280', # gray
        }
        color = colors.get(obj.delivery_type, '#6b7280')
        label = obj.get_delivery_display_name()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">{}</span>',
            color, label
        )

    @admin.display(description='Comprobante')
    def invoice_badge(self, obj):
        colors = {
            'A': '#7c3aed',           # violet
            'B': '#0284c7',           # sky blue
            'unspecified': '#6b7280', # gray
        }
        color = colors.get(obj.invoice_type, '#6b7280')
        label = obj.get_invoice_display_name()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">{}</span>',
            color, label
        )


class OrderRevocationAdminForm(forms.ModelForm):
    """
    Formulario de validación del panel administrativo para revocaciones.
    # REGLA: Exige fundamentación documentada para excepciones y medidas operativas.
    """
    class Meta:
        model = OrderRevocation
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        measures_taken = cleaned_data.get('measures_taken')
        measures_desc = cleaned_data.get('measures_description')
        basis = cleaned_data.get('exception_basis')
        reason = cleaned_data.get('exception_reason')

        # REGLA: Medidas operativas deben tener descripción obligatoria
        if measures_taken and not (measures_desc and measures_desc.strip()):
            self.add_error('measures_description', 'Debe documentar la medida operativa concreta adoptada.')

        # REGLA: Excepción legal requiere causal y fundamento normativo
        if status == 'not_eligible_exception':
            if not basis:
                self.add_error('exception_basis', 'Debe indicar la excepción legal evaluada conforme a la Disp. 954/2025.')
            if not (reason and reason.strip()):
                self.add_error('exception_reason', 'Debe fundamentar por escrito el motivo de no aplicación.')

        return cleaned_data


class OrderRevocationAdmin(admin.ModelAdmin):
    """
    Administración y auditoría de solicitudes de revocación legal (Disp. 954/2025 y 3/2026).
    # REGLA: Trazabilidad fehaciente del plazo de 24 horas y acuse por canal WhatsApp.
    """
    form = OrderRevocationAdminForm
    list_display = [
        'revocation_code',
        'origin_badge',
        'customer_name',
        'contact_display',
        'acknowledgment_badge',
        'measures_badge',
        'status_badge',
        'created_at',
    ]
    list_filter = ['status', 'origin', 'acknowledgment_sent', 'measures_taken', 'created_at']
    search_fields = ['revocation_code', 'customer_name', 'contact_value', 'order_reference']
    readonly_fields = ['revocation_code', 'created_at', 'updated_at']
    fieldsets = (
        ('Identificación de Solicitud', {
            'fields': ('revocation_code', 'origin', 'customer_name', 'contact_method', 'contact_value', 'order_reference', 'order', 'details')
        }),
        ('Cumplimiento y Acuse (Plazo 24 Horas)', {
            'description': 'Control del acuse de recepción y adopción de medidas para efectivizar la revocación.',
            'fields': (
                'acknowledgment_sent',
                'acknowledgment_sent_at',
                'acknowledgment_channel',
                'acknowledged_by',
                'measures_taken',
                'measures_description',
                'measures_taken_at',
            )
        }),
        ('Resolución y Excepciones Legales', {
            'fields': (
                'status',
                'handled_by',
                'contacted_at',
                'resolved_at',
                'exception_basis',
                'exception_reason',
                'internal_notes',
            )
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        })
    )

    @admin.display(description='Canal')
    def origin_badge(self, obj):
        if obj.origin == 'web':
            return format_html('<span style="background-color: #0284c7; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">Web</span>')
        return format_html('<span style="background-color: #16a34a; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">WhatsApp</span>')

    @admin.display(description='Contacto')
    def contact_display(self, obj):
        method = obj.get_contact_method_display()
        return format_html('<span style="font-size: 11px;"><strong>{}</strong>: {}</span>', method, obj.contact_value)

    @admin.display(description='Acuse Cliente')
    def acknowledgment_badge(self, obj):
        if obj.acknowledgment_sent:
            return format_html('<span style="background-color: #16a34a; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">✅ Acuse Emitido</span>')
        if obj.origin == 'whatsapp':
            return format_html(
                '<span style="background-color: #dc2626; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 700; border: 1px solid #b91c1c;">⚠️ Acuse WhatsApp Pendiente</span>'
            )
        return format_html('<span style="background-color: #eab308; color: black; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">Pendiente</span>')

    @admin.display(description='Medidas 24hs')
    def measures_badge(self, obj):
        if obj.measures_taken:
            return format_html('<span style="background-color: #059669; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">✅ Medidas Iniciadas</span>')
        return format_html('<span style="background-color: #d97706; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">⏳ Pendiente</span>')

    @admin.display(description='Estado')
    def status_badge(self, obj):
        colors = {
            'pending': '#eab308',
            'contacted': '#0284c7',
            'in_review': '#6366f1',
            'resolved': '#16a34a',
            'not_eligible_exception': '#dc2626',
            'cancelled': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        text_color = 'black' if obj.status == 'pending' else 'white'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">{}</span>',
            color, text_color, obj.get_status_display()
        )

    def save_model(self, request, obj, form, change):
        """
        # REGLA: Genera código inmutable al crear manualmente e infiere operador responsable.
        """
        if not change and not obj.revocation_code:
            obj.revocation_code = RevocationService.generate_revocation_code()

        if obj.measures_taken and not obj.measures_taken_at:
            obj.measures_taken_at = timezone.now()

        if obj.acknowledgment_sent and not obj.acknowledgment_sent_at:
            obj.acknowledgment_sent_at = timezone.now()
            if not obj.acknowledgment_channel:
                obj.acknowledgment_channel = obj.origin

        if obj.acknowledgment_sent and not obj.acknowledged_by and request.user.is_authenticated:
            obj.acknowledged_by = request.user

        if not obj.handled_by and request.user.is_authenticated:
            obj.handled_by = request.user

        super().save_model(request, obj, form, change)


admin.site.register(Order, OrderAdmin)
admin.site.register(Payment)
admin.site.register(OrderRevocation, OrderRevocationAdmin)
admin.site.register(OrderProduct)
from django.contrib import admin
from django.utils.html import format_html
from .models import Order, Payment, OrderProduct


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


admin.site.register(Order, OrderAdmin)
admin.site.register(Payment)
admin.site.register(OrderProduct)
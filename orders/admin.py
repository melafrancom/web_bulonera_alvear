from django.contrib import admin
from .models import Order, Payment, OrderProduct

# Register your models here.
class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = ('payment', 'user', 'product', 'quantity', 'purchase_price', 'ordered')
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'full_name', 'delivery_type', 'invoice_type', 'phone', 'email', 'order_total', 'status', 'is_ordered', 'created_at']
    list_filter = ['delivery_type', 'invoice_type', 'status', 'is_ordered']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email', 'doc_number', 'business_name']
    list_per_page = 20
    inlines = [OrderProductInline]



# Register your models here.
admin.site.register(Order, OrderAdmin)
admin.site.register(Payment)
admin.site.register(OrderProduct)
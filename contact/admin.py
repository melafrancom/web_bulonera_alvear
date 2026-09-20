from django.contrib import admin
from .models import ContactOption


@admin.register(ContactOption)
class ContactOptionAdmin(admin.ModelAdmin):
    """Administración de mensajes de contacto recibidos."""
    list_display = ('name', 'email', 'contact_method', 'subject', 'created_at')
    list_filter = ('contact_method', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'contact_method', 'subject', 'message', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        """Los mensajes de contacto provienen de usuarios externos; no se crean manualmente en admin."""
        return False

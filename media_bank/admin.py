"""Media Bank Admin"""
from django.contrib import admin
from django.utils.html import format_html
from .models import ImageAsset


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ('thumbnail_preview', 'name', 'image_type', 'file', 'uploaded_at')
    list_filter = ('image_type', 'uploaded_at')
    search_fields = ('name', 'alt_text')
    readonly_fields = ('thumbnail_preview_large', 'uploaded_at')
    
    fieldsets = (
        ('Tipo de Imagen', {
            'fields': ('image_type',)
        }),
        ('Imagen', {
            'fields': ('file', 'thumbnail_preview_large')
        }),
        ('Información', {
            'fields': ('name', 'alt_text', 'uploaded_at')
        }),
    )

    def thumbnail_preview(self, obj):
        """Thumbnail seguro en la lista para prevenir Stored XSS."""
        if obj.file and obj.file.name:
            return format_html(
                '<img src="{}" alt="{}" style="width:60px; height:60px; object-fit:cover; border-radius:4px;" />',
                obj.file.url,
                obj.alt_text or obj.name or ''
            )
        return "—"
    thumbnail_preview.short_description = "Preview"

    def thumbnail_preview_large(self, obj):
        """Preview grande seguro en el formulario para prevenir Stored XSS."""
        if obj.file and obj.file.name:
            return format_html(
                '<img src="{}" alt="{}" style="max-width:400px; border-radius:8px;" />',
                obj.file.url,
                obj.alt_text or obj.name or ''
            )
        return "—"
    thumbnail_preview_large.short_description = "Vista previa"

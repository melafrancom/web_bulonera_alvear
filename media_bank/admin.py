"""Media Bank Admin"""
from django.contrib import admin
from django.utils.safestring import mark_safe
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
        """Thumbnail en la lista."""
        if obj.file:
            return mark_safe(
                f'<img src="{obj.file.url}" '
                f'style="width:60px; height:60px; object-fit:cover; border-radius:4px;" />'
            )
        return "—"
    thumbnail_preview.short_description = "Preview"

    def thumbnail_preview_large(self, obj):
        """Preview grande en el formulario."""
        if obj.file:
            return mark_safe(
                f'<img src="{obj.file.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        return "—"
    thumbnail_preview_large.short_description = "Vista previa"

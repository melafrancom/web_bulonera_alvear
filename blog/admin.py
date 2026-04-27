"""Blog Admin - Django admin configuration"""
from django.contrib import admin
from django.utils import timezone
from ckeditor.widgets import CKEditorWidget
from blog.models import Post, SocialMetadata, PostTag


class SocialMetadataInline(admin.StackedInline):
    """Inline para editar metadata de red social dentro del Post"""
    model = SocialMetadata
    extra = 0
    max_num = 1
    fields = ('platform', 'original_url', 'embed_url', 'embed_code', 'captured_at')
    readonly_fields = ('captured_at',)


# Acciones de publicación en lote
@admin.action(description="✅ Publicar posts seleccionados")
def make_published(modeladmin, request, queryset):
    """
    Acción bulk: publica posts y asigna published_date si está vacío.
    """
    count = queryset.filter(is_published=False).update(
        is_published=True,
        published_date=timezone.now()
    )
    modeladmin.message_user(request, f"✅ {count} post(s) publicados correctamente.")


@admin.action(description="❌ Despublicar posts seleccionados")
def make_unpublished(modeladmin, request, queryset):
    """Acción bulk: despublica posts seleccionados."""
    count = queryset.filter(is_published=True).update(is_published=False)
    modeladmin.message_user(request, f"❌ {count} post(s) despublicados correctamente.")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Admin para gestión de posts del blog"""
    list_display = [
        'title', 'post_type', 'is_published', 'published_date', 'views_count', 'author'
    ]
    list_filter = ['post_type', 'is_published', 'created_date', 'tags']
    search_fields = ['title', 'content', 'excerpt']
    autocomplete_fields = ['featured_image', 'tags']
    inlines = [SocialMetadataInline]
    readonly_fields = ['views_count', 'created_date', 'modified_date', 'author']
    actions = [make_published, make_unpublished]
    
    fieldsets = (
        ('Contenido', {
            'fields': ('title', 'slug', 'post_type', 'content', 'excerpt'),
            'description': 'El slug se genera automáticamente del título si lo dejas vacío. Puedes personalizarlo si lo deseas.'
        }),
        ('Media', {
            'fields': ('featured_image', 'image_alt')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'description': 'Meta tags para optimización en motores de búsqueda'
        }),
        ('Publicación', {
            'fields': ('author', 'is_published', 'published_date', 'tags'),
            'description': 'Controla la visibilidad pública del post y su fecha de publicación'
        }),
        ('Métricas', {
            'fields': ('views_count', 'created_date', 'modified_date'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-asignar autor en creación"""
        if not change:  # Si es nueva creación
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Usar CKEditorWidget para el campo content"""
        if db_field.name == 'content':
            kwargs['widget'] = CKEditorWidget(config_name='blog')
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(PostTag)
class PostTagAdmin(admin.ModelAdmin):
    """Admin para gestión de tags del blog"""
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    
    def get_readonly_fields(self, request, obj=None):
        """
        Slug es readonly SOLO en edición (obj existe).
        En creación, se genera automáticamente via JS (prepopulated_fields).
        """
        if obj:  # Editando objeto existente
            return ['slug']
        return []  # En creación, lo genera JS

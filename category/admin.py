from django.contrib import admin
from django.utils.safestring import mark_safe

#local
from .models import Category, SubCategory, FeaturedCategory, NavbarItem

class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    prepopulated_fields = {'slug': ('subcategory_name',)}
    extra = 1
    autocomplete_fields = ['image_asset']

class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('category_name',)}
    list_display = ('category_name', 'slug')
    search_fields = ['category_name', 'slug']
    inlines = [SubCategoryInline]
    autocomplete_fields = ['image']
    readonly_fields = ['image_preview_method']
    
    fieldsets = (
        ("Información General", {"fields": ("category_name", "description", "slug", "image", "cat_image", "image_preview_method")}),
        ("Contenido SEO (Texto Maestro)", {
            "fields": ("rich_description",),
            "description": "Texto HTML que aparece en la página de la categoría. Usar para tables de medidas y keywords."
        }),
        ("Metadatos SEO", {"fields": ("meta_title", "meta_description")}),
    )
    
    def image_preview_method(self, obj):
        """Preview readonly de la imagen seleccionada en el FK."""
        if obj.image and obj.image.file and obj.image.file.name:
            return mark_safe(
                f'<img src="{obj.image.file.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen"

class SubCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('subcategory_name',)}
    list_display = ('subcategory_name', 'category', 'slug', 'image')
    list_filter = ('category',)
    search_fields = ['subcategory_name', 'slug']  # Necesario para autocomplete_fields
    autocomplete_fields = ['image_asset']
    readonly_fields = ['image_preview_method']
    
    fieldsets = (
        ("Información General", {"fields": ("subcategory_name", "category", "slug", "image_asset", "image", "image_preview_method")}),
        ("Contenido SEO (Texto Maestro)", {
            "fields": ("rich_description",),
            "description": "Texto HTML que aparece en la página de la subcategoría."
        }),
        ("Metadatos SEO", {"fields": ("meta_title", "meta_description")}),
    )
    
    def image_preview_method(self, obj):
        """Preview readonly de la imagen seleccionada en el FK."""
        if obj.image_asset and obj.image_asset.file and obj.image_asset.file.name:
            return mark_safe(
                f'<img src="{obj.image_asset.file.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen"
    

class FeaturedCategoryAdmin(admin.ModelAdmin):
    list_display = ('category', 'position', 'is_active')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)

class NavbarItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'item_type', 'category', 'custom_url', 'position', 'is_active')
    list_editable = ('position', 'is_active')
    list_filter = ('item_type', 'is_active')
    search_fields = ('label', 'custom_url')
    autocomplete_fields = ['category']

admin.site.register(Category, CategoryAdmin)
admin.site.register(SubCategory, SubCategoryAdmin)
admin.site.register(FeaturedCategory, FeaturedCategoryAdmin)
admin.site.register(NavbarItem, NavbarItemAdmin)




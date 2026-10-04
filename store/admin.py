from django.contrib import admin
import admin_thumbnails
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils.html import format_html
import pandas as pd
import csv
import io
import openpyxl
from io import TextIOWrapper
from django.utils.text import slugify
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os
import uuid
from django.db import transaction
from pathlib import Path
from django.conf import settings

# local:
from .models import Product, Variation, ReviewRating, ProductGallery, CarouselImage, ProductSearch, FAQCategory, FAQ, HomeSection, HomeSectionProduct, PromoBanner, ProductTag
from category.models import Category, SubCategory
from store.web.forms import ProductImportForm
from .utils import ImageProcessor



class ProductGalleryInLine(admin.TabularInline):
    model = ProductGallery
    extra = 1
    fields = ['image_asset', 'image', 'image_preview', 'alt']
    readonly_fields = ('image', 'image_preview')
    verbose_name = "Imagen adicional"
    verbose_name_plural = "Galería de imágenes"
    autocomplete_fields = ['image_asset']

    def image_preview(self, obj):
        if obj.image_asset and obj.image_asset.file:
            return format_html('<img src="{}" style="max-height: 100px; border-radius:4px;"/>', obj.image_asset.file.url)
        elif obj.image:
            return format_html('<img src="{}" style="max-height: 100px; border-radius:4px;"/>', obj.image.url)
        return "—"
    image_preview.short_description = "Vista previa"

class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'price', 'stock', 'is_on_sale', 'category', 'display_subcategories', 'modified_date', 'is_available')
    list_editable = ('price', 'stock', 'is_available', 'is_on_sale')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductGalleryInLine]
    search_fields = ('code', 'name', 'description')
    readonly_fields = ['created_date', 'modified_date', 'image_preview_method']  # ⬅ evitamos modificar fechas manualmente
    list_filter = ('category', 'subcategories', 'tags', 'is_available', 'is_on_sale', 'brand', 'condition')
    filter_horizontal = ('subcategories', 'tags')
    autocomplete_fields = ['image']
    actions = ['make_available', 'make_unavailable']
    # Agrega una url personalizada
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-products/', self.admin_site.admin_view(self.import_products), name='import_products'),
            path('update-prices/', self.admin_site.admin_view(self.update_prices), name='update_prices'),
        ]
        return custom_urls + urls
    
    def image_preview_method(self, obj):
        """Preview readonly de la imagen seleccionada en el FK."""
        if obj.image and obj.image.file and obj.image.file.name:
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px;" />',
                obj.image.file.url
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen"
    
    def import_products(self, request):
        if request.method == 'POST':
            form = ProductImportForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES['file']
                try:
                    from store.services import ProductService
                    import_result = ProductService.import_from_file(file)
                    self._report_import_result(request, import_result)
                    return redirect('admin:store_product_changelist')
                except Exception as e:
                    messages.error(request, f"Error al importar productos: {str(e)}")
            else:
                messages.error(request, "El formulario no es válido. Verifique el archivo.")
        else:
            form = ProductImportForm()
        
        return render(request, 'admin/store/product/import_products.html', {'form': form})

    def update_prices(self, request):
        if request.method == 'POST':
            form = ProductImportForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES['file']
                try:
                    from store.services import ProductService
                    update_result = ProductService.update_prices_from_file(file)
                    self._report_update_result(request, update_result)
                    return redirect('admin:store_product_changelist')
                except Exception as e:
                    messages.error(request, f"Error al actualizar precios: {str(e)}")
            else:
                messages.error(request, "El formulario no es válido. Verifique el archivo.")
        else:
            form = ProductImportForm()
        
        return render(request, 'admin/store/product/update_prices.html', {'form': form})

    def _report_import_result(self, request, result):
        success_count = result.created + result.updated
        if result.errors > 0:
            error_sample = [f"Fila {row}: {msg}" for row, msg in result.error_details[:5]]
            error_message = "<br>".join(error_sample)
            if result.errors > 5:
                error_message += f"<br>... y {result.errors - 5} errores más."
                
            messages.warning(request, 
                            f"Se procesaron {success_count} productos ({result.created} creados, {result.updated} actualizados), pero {result.errors} fallaron. "
                            f"Ejemplos de errores:<br>{error_message}", 
                            extra_tags='safe')
        else:
            msg = f"Se importaron/actualizaron correctamente {success_count} productos ({result.created} creados, {result.updated} actualizados)."
            if result.image_warnings > 0:
                msg += f" Hubo {result.image_warnings} advertencias con imágenes."
            if hasattr(result, 'tags_created') and getattr(result, 'tags_created'):
                msg += f"<br>Nuevos tags creados: {', '.join(getattr(result, 'tags_created'))}."
            messages.success(request, msg, extra_tags='safe')

    def _report_update_result(self, request, result):
        if result.errors > 0:
            error_sample = [f"Fila {row}: {msg}" for row, msg in result.error_details[:5]]
            error_message = "<br>".join(error_sample)
            if result.errors > 5:
                error_message += f"<br>... y {result.errors - 5} errores más."
                
            messages.warning(request, 
                            f"Se actualizaron los precios de {result.updated} productos, pero {result.errors} fallaron. "
                            f"Ejemplos de errores:<br>{error_message}", 
                            extra_tags='safe')
        else:
            messages.success(request, f"Se actualizaron correctamente los precios de {result.updated} productos.")
        
    def process_price_update(self, products_data):
        """Procesar y actualizar precios de productos desde los datos analizados"""
        from store.services import ProductService
        
        success_count = 0
        failed_count = 0
        validation_errors = []
        
        for item in products_data:
            try:
                # Omitir si no se proporciona código o precio o si son NaN
                if 'code' not in item or not item['code'] or pd.isna(item['code']):
                    validation_errors.append(f"Fila rechazada: Falta el código del producto")
                    failed_count += 1
                    continue
                    
                if 'price' not in item or not item['price'] or pd.isna(item['price']):
                    validation_errors.append(f"Producto {item['code']}: Falta el precio")
                    failed_count += 1
                    continue
                
                # Convertir código a string para asegurar la búsqueda correcta
                product_code = str(item['code']).strip()
                
                # Verificar si el producto existe
                try:
                    product = Product.objects.get(code=product_code)
                    
                    # Sanitizar precio usando el método canónico de services.py
                    try:
                        product.price = ProductService._sanitize_price(item['price'])
                        product.save(update_fields=['price', 'modified_date'])
                        success_count += 1
                    except ValueError as e:
                        validation_errors.append(f"Producto {product_code}: {str(e)}")
                        failed_count += 1
                    
                except Product.DoesNotExist:
                    validation_errors.append(f"Producto {product_code}: No existe en la base de datos")
                    failed_count += 1
                    
            except Exception as e:
                error_msg = f"Error al actualizar precio para producto {item.get('code', 'desconocido')}: {str(e)}"
                print(error_msg)
                validation_errors.append(error_msg)
                failed_count += 1
        
        # Registrar errores en el log
        if validation_errors:
            print(f"\nErrores durante la actualización de precios:")
            for error in validation_errors:
                print(f"- {error}")
        
        return {
            'success': success_count,
            'failed': failed_count,
            'validation_errors': validation_errors
        }
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_import_button'] = True
        extra_context['show_price_update_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def display_subcategories(self, obj):
        return ", ".join([subcategory.subcategory_name for subcategory in obj.subcategories.all()])
    display_subcategories.short_description = 'Subcategories'


class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('product', 'variation_category', 'variation_value', 'is_active')



# Register your models here.
admin.site.register(Product, ProductAdmin)
admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)
admin.site.register(ProductGallery)



##NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:

class CarouselImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'position', 'is_active', 'created_date')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'product__name')
    readonly_fields = (
        'image_preview_method', 'image_mobile_preview_method',
        'image_tablet_preview_method', 'image_large_preview_method',
        'created_date'
    )
    autocomplete_fields = [
        'image_asset', 'image_mobile_asset',
        'image_tablet_asset', 'image_large_asset'
    ]
    
    def image_preview_method(self, obj):
        """Preview readonly de la imagen seleccionada en el FK."""
        if obj.image_asset and obj.image_asset.file and obj.image_asset.file.name:
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px;" />',
                obj.image_asset.file.url
            )
        elif obj.image and obj.image.name:
            return format_html(
                '<img src="{}" style="max-width:400px; border-radius:8px;" />',
                obj.image.url
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen (Desktop)"

    def image_mobile_preview_method(self, obj):
        """Preview readonly de la imagen móvil (Art Direction)."""
        if obj.image_mobile_asset and obj.image_mobile_asset.file and obj.image_mobile_asset.file.name:
            return format_html(
                '<img src="{}" style="max-width:300px; border-radius:8px;" />',
                obj.image_mobile_asset.file.url
            )
        elif obj.image_mobile and obj.image_mobile.name:
            return format_html(
                '<img src="{}" style="max-width:300px; border-radius:8px;" />',
                obj.image_mobile.url
            )
        return "—"
    image_mobile_preview_method.short_description = "Vista previa de imagen (Mobile)"

    def image_tablet_preview_method(self, obj):
        """Preview readonly de la imagen tablet (Art Direction)."""
        if obj.image_tablet_asset and obj.image_tablet_asset.file and obj.image_tablet_asset.file.name:
            return format_html(
                '<img src="{}" style="max-width:350px; border-radius:8px;" />',
                obj.image_tablet_asset.file.url
            )
        return "—"
    image_tablet_preview_method.short_description = "Vista previa de imagen (Tablet)"

    def image_large_preview_method(self, obj):
        """Preview readonly de la imagen large (Art Direction)."""
        if obj.image_large_asset and obj.image_large_asset.file and obj.image_large_asset.file.name:
            return format_html(
                '<img src="{}" style="max-width:500px; border-radius:8px;" />',
                obj.image_large_asset.file.url
            )
        return "—"
    image_large_preview_method.short_description = "Vista previa de imagen (Large Monitor)"

admin.site.register(CarouselImage, CarouselImageAdmin)

# Si quieres ver las estadísticas de búsqueda en el admin
class ProductSearchAdmin(admin.ModelAdmin):
    list_display = ('product', 'search_count', 'user', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'user__email')
    readonly_fields = ('product', 'user', 'session_key', 'search_count', 'created_at', 'updated_at')

admin.site.register(ProductSearch, ProductSearchAdmin)


class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ['question', 'answer', 'subcategory', 'order', 'is_active']
    raw_id_fields = ['subcategory']  # Añade un selector de búsqueda para subcategorías

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']
    inlines = [FAQInline]
    search_fields = ['name']
    
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'subcategory', 'is_active', 'order']
    list_filter = ['category', 'is_active', 'subcategory__category']
    search_fields = ['question', 'answer', 'subcategory__subcategory_name']
    raw_id_fields = ['subcategory']
    list_editable = ['is_active', 'order']
    autocomplete_fields = ['subcategory']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 
            'subcategory', 
            'subcategory__category'
        )


# ============================================================================
# HOME PAGE BUILDER — Admin para Secciones Dinámicas
# ============================================================================

class HomeSectionProductInline(admin.TabularInline):
    """Inline para seleccionar productos manualmente en cada sección."""
    model = HomeSectionProduct
    extra = 0
    fields = ['product', 'position']
    autocomplete_fields = ['product']
    ordering = ['position']
    verbose_name = "Producto seleccionado"
    verbose_name_plural = "Productos seleccionados (manual)"


class PromoBannerInline(admin.StackedInline):
    """Inline para subir banners dentro de una sección banner_*."""
    model = PromoBanner
    extra = 0
    fields = [
        ('title', 'alt_text'),
        ('image_desktop_asset', 'image_large_asset'),      # Desktop + Large juntos
        ('image_tablet_asset', 'image_mobile_asset'),       # Tablet + Mobile juntos
        ('image_desktop', 'image_mobile'),
        ('url', 'open_new_tab'),
        ('link_product', 'link_category', 'link_params'),
        ('position', 'is_active'),
    ]
    autocomplete_fields = [
        'image_desktop_asset', 'image_large_asset',
        'image_tablet_asset', 'image_mobile_asset',
        'link_product', 'link_category'
    ]
    verbose_name = "Banner"
    verbose_name_plural = "Banners de esta sección"


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'section_type', 'source_type',
                    'category', 'product_count_display', 'is_active')
    list_display_links = ('title',)
    list_editable = ('position', 'is_active')
    list_filter = ('section_type', 'is_active', 'source_type')
    ordering = ('position',)
    search_fields = ('title',)
    raw_id_fields = ['category']
    actions = ['auto_populate_products']

    fieldsets = (
        ('Configuración General', {
            'fields': ('title', 'section_type', 'position', 'is_active', 'highlight_color')
        }),
        ('Banda CTA (solo si section_type = cta_band)', {
            'fields': ('cta_text',),
            'classes': ('collapse',),
            'description': 'Texto del llamado a la acción. Si se deja vacío, se usa el campo "Título" como texto.'
        }),
        ('Fuente de Productos (solo para carruseles)', {
            'fields': ('source_type', 'category', 'max_products'),
            'classes': ('collapse',),
            'description': 'Si selecciona productos manualmente abajo, estos campos se ignoran.'
        }),
    )

    def get_inlines(self, request, obj=None):
        """Mostrar inlines según el tipo de sección."""
        if obj:
            # Banners y carruseles de categorías usan PromoBanner
            if obj.section_type.startswith('banner_') or \
               obj.section_type in ('categories_carousel', 'categories_featured'):
                return [PromoBannerInline]
            # Carruseles de productos usan HomeSectionProduct
            elif obj.section_type == 'product_carousel':
                return [HomeSectionProductInline]
        return []

    def product_count_display(self, obj):
        if obj.section_type == 'product_carousel':
            manual = obj.home_section_products.count()
            if manual > 0:
                return f"✋ {manual} manuales"
            return f"🤖 Auto ({obj.get_source_type_display()})"
        elif obj.section_type.startswith('banner_') or \
             obj.section_type in ('categories_carousel', 'categories_featured'):
            return f"🖼️ {obj.banners.filter(is_active=True).count()} imágenes"
        return "—"
    product_count_display.short_description = "Contenido"

    def auto_populate_products(self, request, queryset):
        """
        Acción admin: toma los productos auto-generados por source_type
        y los convierte en selección manual editable.
        """
        from store.services import HomeSectionService
        from store.models import HomeSectionProduct
        
        count = 0
        for section in queryset.filter(section_type='product_carousel'):
            products = HomeSectionService.get_recommended_products(section)
            for i, product in enumerate(products):
                HomeSectionProduct.objects.get_or_create(
                    section=section, product=product,
                    defaults={'position': i}
                )
            count += 1
        
        self.message_user(request, f"Se auto-poblaron {count} secciones con productos sugeridos.")
    auto_populate_products.short_description = "🤖 Auto-poblar con productos recomendados"


@admin.register(HomeSectionProduct)
class HomeSectionProductAdmin(admin.ModelAdmin):
    list_display = ('section', 'product', 'position')
    list_editable = ('position',)
    list_filter = ('section', )
    search_fields = ('product__name', 'section__title')
    autocomplete_fields = ['section', 'product']
    ordering = ('section', 'position')


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ('section', 'title', 'position', 'is_active', 'link_type_display')
    list_editable = ('position', 'is_active')
    list_filter = ('section', 'is_active', 'open_new_tab')
    search_fields = ('title', 'alt_text', 'url')
    raw_id_fields = ['link_product', 'link_category']
    autocomplete_fields = [
        'image_desktop_asset', 'image_large_asset',
        'image_tablet_asset', 'image_mobile_asset'
    ]
    ordering = ('section', 'position')
    
    fieldsets = (
        ('Información General', {
            'fields': ('section', 'title', 'alt_text', 'position', 'is_active')
        }),
        ('Imágenes (Art Direction 4-layer)', {
            'fields': (
                ('image_desktop_asset', 'image_large_asset'),
                ('image_tablet_asset', 'image_mobile_asset'),
                ('image_desktop', 'image_mobile'),
            ),
            'description': '[NUEVOS] Desktop/Tablet/Mobile/Large desde Banco (recomendado). [LEGACY] Imágenes directas debajo (compatibilidad).'
        }),
        ('Sistema de Enlaces (Prioridad: URL > Producto > Categoría)', {
            'fields': ('url', 'link_product', 'link_category', 'link_params', 'open_new_tab'),
            'description': 'Defina SOLO uno: URL para externo, Producto/Categoría para interno.'
        }),
    )
    
    def link_type_display(self, obj):
        if obj.url:
            return "🌐 URL"
        elif obj.link_product:
            return "📦 Producto"
        elif obj.link_category:
            return "📂 Categoría"
        return "—"
    link_type_display.short_description = "Tipo de enlace"

@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active',)
    search_fields = ('name', 'slug')

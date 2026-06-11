from django.contrib import admin
import admin_thumbnails
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.utils.safestring import mark_safe
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
from .models import Product, Variation, ReviewRating, ProductGallery, CarouselImage, ProductSearch, FAQCategory, FAQ, HomeSection, HomeSectionProduct, PromoBanner
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
            return mark_safe(f'<img src="{obj.image_asset.file.url}" style="max-height: 100px; border-radius:4px;"/>')
        elif obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="max-height: 100px; border-radius:4px;"/>')
        return "—"
    image_preview.short_description = "Vista previa"

class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'price', 'stock', 'is_on_sale', 'category', 'display_subcategories', 'modified_date', 'is_available')
    list_editable = ('price', 'stock', 'is_available', 'is_on_sale')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductGalleryInLine]
    search_fields = ('code', 'name', 'description')
    readonly_fields = ['created_date', 'modified_date', 'image_preview_method']  # ⬅ evitamos modificar fechas manualmente
    list_filter = ('category', 'subcategories', 'is_available', 'is_on_sale', 'brand', 'condition')
    filter_horizontal = ('subcategories',)
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
            return mark_safe(
                f'<img src="{obj.image.file.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen"
    
    def import_products(self, request):
        if request.method == 'POST':
            form = ProductImportForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES['file']
                ext = os.path.splitext(file.name)[1]
                
                try:
                    if ext.lower() == '.xlsx':
                        products_data = self.parse_excel(file)
                    elif ext.lower() == '.csv':
                        products_data = self.parse_csv(file)
                    
                    # Procesar los datos e importar productos
                    import_result = self.process_import(products_data)
                    
                    if import_result['validation_errors']:
                        # Mostrar los primeros 5 errores de validación (para no abrumar)
                        error_sample = import_result['validation_errors'][:5]
                        error_message = "<br>".join(error_sample)
                        if len(import_result['validation_errors']) > 5:
                            error_message += f"<br>... y {len(import_result['validation_errors']) - 5} errores más."
                        
                        messages.warning(request, 
                                        f"Se importaron {import_result['success']} productos, pero {import_result['failed']} fallaron. "
                                        f"Ejemplos de errores:<br>{error_message}", 
                                        extra_tags='safe')
                    else:
                        messages.success(request, 
                                        f"Se importaron correctamente {import_result['success']} productos. "
                                        f"{import_result['image_errors']} imágenes no se encontraron en el servidor.")
                    
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
                ext = os.path.splitext(file.name)[1]
                
                try:
                    if ext.lower() == '.xlsx':
                        products_data = self.parse_excel(file)
                    elif ext.lower() == '.csv':
                        products_data = self.parse_csv(file)
                    
                    # Procesar los datos y actualizar precios
                    update_result = self.process_price_update(products_data)
                    
                    if update_result['validation_errors']:
                        # Mostrar los primeros 5 errores de validación (para no abrumar)
                        error_sample = update_result['validation_errors'][:5]
                        error_message = "<br>".join(error_sample)
                        if len(update_result['validation_errors']) > 5:
                            error_message += f"<br>... y {len(update_result['validation_errors']) - 5} errores más."
                        
                        messages.warning(request, 
                                        f"Se actualizaron los precios de {update_result['success']} productos, pero {update_result['failed']} fallaron. "
                                        f"Ejemplos de errores:<br>{error_message}", 
                                        extra_tags='safe')
                    else:
                        messages.success(request, 
                                        f"Se actualizaron correctamente los precios de {update_result['success']} productos.")
                    
                    return redirect('admin:store_product_changelist')
                except Exception as e:
                    messages.error(request, f"Error al actualizar precios: {str(e)}")
            else:
                messages.error(request, "El formulario no es válido. Verifique el archivo.")
        else:
            form = ProductImportForm()
        
        return render(request, 'admin/store/product/update_prices.html', {'form': form})

    def parse_excel(self, file):
        """Analizar archivo Excel y devolver datos como lista de diccionarios"""
        # Delegar al parser canónico de services.py
        from store.services import ProductService
        return ProductService._parse_file(file)
    
    def parse_csv(self, file):
        """Analizar archivo CSV y devolver datos como lista de diccionarios"""
        # Delegar al parser canónico de services.py
        from store.services import ProductService
        return ProductService._parse_file(file)
    
    def find_image_in_directory(self, image_path, directory):
        """
        Busca una imagen en el directorio especificado, considerando la versión sanitizada del nombre.
        Puede recibir una ruta completa o solo el nombre del archivo.
        Retorna el nombre del archivo si lo encuentra, None si no.
        """
        if not os.path.exists(directory):
            return None
            
        # Extraer solo el nombre del archivo si se proporciona una ruta completa
        image_name = os.path.basename(image_path.strip())
        
        # Sanitizar el nombre de búsqueda
        search_name = slugify(image_name)
        if not search_name:
            return None

        # Buscar en el directorio y sus subdirectorios
        for root, dirs, files in os.walk(directory):
            for filename in files:
                # Comparar versiones sanitizadas
                if slugify(filename) == search_name:
                    return filename
                # También intentar coincidir con el nombre exacto
                elif filename.lower() == image_name.lower():
                    return filename
        
        return None
    def process_import(self, products_data):
        """Procesar e importar productos desde los datos analizados"""
        success_count = 0
        failed_count = 0
        image_errors = []
        validation_errors = []
        processed_subcategories = set()  # Para trackear subcategorías ya procesadas
        
        try:
            for item in products_data:
                try:
                    # Validar campos obligatorios: code y price
                    if 'code' not in item or not item['code'] or pd.isna(item['code']):
                        validation_errors.append(f"Fila rechazada: Falta el código del producto")
                        failed_count += 1
                        continue
                    
                    if 'price' not in item or not item['price'] or pd.isna(item['price']):
                        validation_errors.append(f"Producto {item['code']}: Falta el precio")
                        failed_count += 1
                        continue
                    
                    # Verificar si el producto ya existe
                    product_exists = Product.objects.filter(code=str(item['code'])).exists()
                    if product_exists:
                        # Actualizar producto existente
                        product = Product.objects.get(code=str(item['code']))
                    else:
                        # Crear nuevo producto
                        product = Product(code=str(item['code']))
                    
                    # Actualizar campos del producto solo si se proporcionan
                    if 'name' in item and item['name'] and not pd.isna(item['name']):
                        product.name = str(item['name'])
                    elif not product_exists:
                        # Si es un producto nuevo, necesitamos un nombre predeterminado
                        product.name = f"Producto {item['code']}"
                    
                        # Procesar diámetro y largo si existen
                    if 'diameter' in item and not pd.isna(item['diameter']):
                        product.diameter = str(item['diameter'])
                    if 'length' in item and not pd.isna(item['length']):
                        product.length = str(item['length'])
                    # Establecer el precio (sabemos que existe porque lo validamos arriba)
                    product.price = float(item['price'])
                    
                    # Campos opcionales
                    if 'description' in item and item['description'] and not pd.isna(item['description']):
                        product.description = str(item['description'])
                    
                    # Google Merchant identifiers
                    if 'gtin' in item and item['gtin'] and not pd.isna(item['gtin']):
                        product.gtin = str(item['gtin'])

                    if 'mpn' in item and item['mpn'] and not pd.isna(item['mpn']):
                        product.mpn = str(item['mpn'])
                        
                    # Google Merchant category
                    if 'google_category' in item and item['google_category'] and not pd.isna(item['google_category']):
                        product.google_category = str(item['google_category'])
                    
                    ################## Campos SEO ##################
                    if 'meta_title' in item and item['meta_title'] and not pd.isna(item['meta_title']):
                        product.meta_title = str(item['meta_title'])

                    if 'meta_description' in item and item['meta_description'] and not pd.isna(item['meta_description']):
                        product.meta_description = str(item['meta_description'])

                    if 'meta_keywords' in item and item['meta_keywords'] and not pd.isna(item['meta_keywords']):
                        product.meta_keywords = str(item['meta_keywords'])
                    
                    # Manejar stock correctamente para evitar el error NaN
                    if 'stock' in item and item['stock'] and not pd.isna(item['stock']):
                        try:
                            product.stock = int(float(item['stock']))
                        except (ValueError, TypeError):
                            product.stock = 0  # Valor por defecto si hay error de conversión
                    else:
                        # Valor predeterminado para stock si no se proporciona
                        product.stock = 0
                    
                    # Manejar categoría
                    if 'category' in item and item['category'] and not pd.isna(item['category']):
                        try:
                            category = Category.objects.get(category_name=str(item['category']))
                            product.category = category
                        except Category.DoesNotExist:
                            # Crear nueva categoría si no existe
                            category = Category.objects.create(
                                category_name=str(item['category']),
                                slug=slugify(str(item['category']))
                            )
                            product.category = category
                    elif not product_exists or not product.category:
                        # Si es un producto nuevo sin categoría, asignar una categoría predeterminada
                        try:
                            category = Category.objects.get(category_name="Sin categoría")
                        except Category.DoesNotExist:
                            category = Category.objects.create(
                                category_name="Sin categoría",
                                slug="sin-categoria"
                            )
                        product.category = category
                    
                    # Otros campos
                    if 'brand' in item and item['brand'] and not pd.isna(item['brand']):
                        product.brand = str(item['brand'])
                    
                    if 'condition' in item and item['condition'] and not pd.isna(item['condition']):
                        product.condition = str(item['condition'])
                    
                    #Especificaciones adicionales (opcionales)
                    if 'norm' in item and item['norm'] and not pd.isna(item['norm']):
                        product.norm = str(item['norm'])
                    if 'grade' in item and item['grade'] and not pd.isna(item['grade']):
                        product.grade = str(item['grade'])
                    if 'material' in item and item['material'] and not pd.isna(item['material']):
                        product.material = str(item['material'])
                    if 'colour' in item and item['colour'] and not pd.isna(item['colour']):
                        product.colour = str(item['colour'])
                    if 'type' in item and item['type'] and not pd.isna(item['type']):
                        product.type = str(item['type'])
                    if 'form' in item and item['form'] and not pd.isna(item['form']):
                        product.form = str(item['form'])
                    if 'thread_formats' in item and item['thread_formats'] and not pd.isna(item['thread_formats']):
                        product.thread_formats = str(item['thread_formats'])
                    if 'origin' in item and item['origin'] and not pd.isna(item['origin']):
                        product.origin = str(item['origin'])
                    
                    # Manejar imagen principal - solo si se proporciona
                    if 'images' in item and item['images'] and not pd.isna(item['images']):
                        image_path = str(item['images']).strip()
                        products_dir = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'original')
                        
                        # Verificar si la imagen existe en el servidor
                        found_image = self.find_image_in_directory(image_path, products_dir)
                        if found_image:
                            # Guardar primero el producto para tener un ID
                            product.save()
                            
                            # Configurar la ruta de la imagen
                            full_image_path = os.path.join(products_dir, found_image)
                            relative_path = os.path.join('photos', 'products', 'original', found_image)
                            product.images = relative_path
                            
                            # Procesar la imagen con ImageProcessor
                            processor = ImageProcessor(full_image_path)
                            if not processor.process_image():
                                image_errors.append(f"Error procesando imagen para producto {item['code']}")
                        else:
                            # Registrar error pero continuar con la importación
                            image_errors.append(f"Imagen principal no encontrada para producto {item['code']}: {image_path}")
                    
                    # Intentar guardar el producto (podría fallar si faltan campos obligatorios del modelo)
                    try:
                        product.save()
                        success_count += 1
                    except Exception as model_error:
                        validation_errors.append(f"Error al guardar producto {item['code']}: {str(model_error)}")
                        failed_count += 1
                        continue
                    
                    # Manejar galería de imágenes adicionales
                    if 'gallery' in item and item['gallery'] and not pd.isna(item['gallery']):
                        # Eliminar imágenes existentes de la galería si se está actualizando
                        if product_exists:
                            ProductGallery.objects.filter(product=product).delete()
                        
                        # Procesar rutas de imágenes separadas por comas
                        gallery_paths = [path.strip() for path in str(item['gallery']).split(',')]
                        
                        for gallery_path in gallery_paths:
                            # Verificar si la imagen existe en el servidor
                            found_gallery_image = self.find_image_in_directory(gallery_path, products_dir)
                            if found_gallery_image:
                                full_gallery_path = os.path.join(products_dir, found_gallery_image)
                                gallery_image = ProductGallery.objects.create(
                                    product=product,
                                    image=os.path.join('photos', 'products', found_gallery_image)
                                )
                                
                                # Procesar imagen de galería
                                processor = ImageProcessor(full_gallery_path)
                                if not processor.process_image():
                                    image_errors.append(f"Error procesando imagen de galería para producto {item['code']}")
                            else:
                                # Registrar error pero continuar
                                image_errors.append(f"Imagen de galería no encontrada para producto {item['code']}: {gallery_path}")
                    
                    # Manejar subcategorías
                    if 'subcategories' in item and item['subcategories'] and not pd.isna(item['subcategories']):
                        subcats = str(item['subcategories']).split(',')
                        for subcat_name in subcats:
                            subcat_name = subcat_name.strip()
                            if subcat_name:  # Verificar que no esté vacío
                                try:
                                    subcat = SubCategory.objects.get(subcategory_name=subcat_name)
                                except SubCategory.DoesNotExist:
                                    # Crear la subcategoría usando el modelo SubCategory
                                    subcat = SubCategory.objects.create(
                                        subcategory_name=subcat_name,
                                        slug=slugify(subcat_name),
                                        category=product.category  # Usar category en lugar de parent
                                    )
                                product.subcategories.add(subcat)
                                # Procesar FAQs solo si esta subcategoría no ha sido procesada
                                if subcat.id not in processed_subcategories and 'faq' in item and item['faq'] and not pd.isna(item['faq']):
                                    # Verificar si ya existen FAQs para esta subcategoría
                                    if not FAQ.objects.filter(subcategory=subcat).exists():
                                        faq_category, _ = FAQCategory.objects.get_or_create(
                                            name='Preguntas específicas de productos',
                                            defaults={'order': 999}
                                        )

                                        # Procesar FAQs
                                        faq_text = str(item['faq'])
                                        import re
                                        faq_pairs = re.findall(r'"([^"]+)"\s*([^,]+)(?:,|$)', faq_text)

                                        for order, (question, answer) in enumerate(faq_pairs):
                                            question = question.strip('¿ ?')
                                            answer = answer.strip()

                                            FAQ.objects.create(
                                                category=faq_category,
                                                subcategory=subcat,
                                                question=f"¿{question}?",
                                                answer=answer,
                                                order=order,
                                                is_active=True
                                            )

                                    processed_subcategories.add(subcat.id)

                    success_count += 1
                    
                except Exception as e:
                    print(f"Error al importar producto {item.get('code', 'desconocido')}: {str(e)}")
                    validation_errors.append(f"Error general para producto {item.get('code', 'desconocido')}: {str(e)}")
                    failed_count += 1
                    
        except Exception as e:
            validation_errors.append(f"Error general en la importación: {str(e)}")
        
        # Registrar errores en el log
        if image_errors or validation_errors:
            print(f"\nErrores durante la importación:")
            for error in validation_errors:
                print(f"- Validación: {error}")
            for error in image_errors:
                print(f"- Imagen: {error}")
        
        return {
            'success': success_count,
            'failed': failed_count,
            'image_errors': len(image_errors),
            'validation_errors': validation_errors
        }
        
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
            return mark_safe(
                f'<img src="{obj.image_asset.file.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        elif obj.image and obj.image.name:
            return mark_safe(
                f'<img src="{obj.image.url}" '
                f'style="max-width:400px; border-radius:8px;" />'
            )
        return "—"
    image_preview_method.short_description = "Vista previa de imagen (Desktop)"

    def image_mobile_preview_method(self, obj):
        """Preview readonly de la imagen móvil (Art Direction)."""
        if obj.image_mobile_asset and obj.image_mobile_asset.file and obj.image_mobile_asset.file.name:
            return mark_safe(
                f'<img src="{obj.image_mobile_asset.file.url}" '
                f'style="max-width:300px; border-radius:8px;" />'
            )
        elif obj.image_mobile and obj.image_mobile.name:
            return mark_safe(
                f'<img src="{obj.image_mobile.url}" '
                f'style="max-width:300px; border-radius:8px;" />'
            )
        return "—"
    image_mobile_preview_method.short_description = "Vista previa de imagen (Mobile)"

    def image_tablet_preview_method(self, obj):
        """Preview readonly de la imagen tablet (Art Direction)."""
        if obj.image_tablet_asset and obj.image_tablet_asset.file and obj.image_tablet_asset.file.name:
            return mark_safe(
                f'<img src="{obj.image_tablet_asset.file.url}" '
                f'style="max-width:350px; border-radius:8px;" />'
            )
        return "—"
    image_tablet_preview_method.short_description = "Vista previa de imagen (Tablet)"

    def image_large_preview_method(self, obj):
        """Preview readonly de la imagen large (Art Direction)."""
        if obj.image_large_asset and obj.image_large_asset.file and obj.image_large_asset.file.name:
            return mark_safe(
                f'<img src="{obj.image_large_asset.file.url}" '
                f'style="max-width:500px; border-radius:8px;" />'
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

from django.contrib import admin
import admin_thumbnails
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
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

#Local:
from .models import Product, Variation, ReviewRating, ProductGallery, CarouselImage, ProductSearch
from category.models import Category, SubCategory
from .forms import ProductImportForm



@admin_thumbnails.thumbnail('image')
class ProductGalleryInLine(admin.TabularInline):
    model = ProductGallery
    extra = 1
    fields = ['image', 'alt']
    verbose_name = "Imagen adicional"
    verbose_name_plural = "Galería de imágenes"

class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'price', 'stock', 'is_on_sale', 'category', 'display_subcategories', 'modified_date', 'is_available')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductGalleryInLine]
    search_fields = ('code', 'name')
    readonly_fields = ['created_date', 'modified_date']  # ⬅ evitamos modificar fechas manualmente
    list_filter = ('category', 'subcategories', 'is_available', 'brand', 'condition')
    filter_horizontal = ('subcategories',)
    # Agrega una url personalizada
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-products/', self.admin_site.admin_view(self.import_products), name='import_products'),
            path('update-prices/', self.admin_site.admin_view(self.update_prices), name='update_prices'),
        ]
        return custom_urls + urls
    
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
        # Lee el archivo Excel con pandas, convirtiendo cadenas vacías a NaN
        df = pd.read_excel(file, keep_default_na=True, na_values=[''])
        
        # Rellenar los valores NaN con None para un manejo más intuitivo en Python
        df = df.where(pd.notna(df), None)
        
        # Convertir DataFrame a lista de diccionarios
        return df.to_dict('records')
    
    def parse_csv(self, file):
        """Analizar archivo CSV y devolver datos como lista de diccionarios"""
        csv_file = TextIOWrapper(file, encoding='utf-8')
        
        # Leer CSV con pandas para manejar NaN de forma consistente
        df = pd.read_csv(csv_file, keep_default_na=True, na_values=[''])
        df = df.where(pd.notna(df), None)
        
        return df.to_dict('records')
    
    def process_import(self, products_data):
        """Procesar e importar productos desde los datos analizados"""
        success_count = 0
        failed_count = 0
        image_errors = []
        validation_errors = []
        
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
                    # Generar slug si aún no está establecido
                    if not product_exists or not product.slug:
                        product.slug = slugify(product.name)
                elif not product_exists:
                    # Si es un producto nuevo, necesitamos un nombre predeterminado
                    product.name = f"Producto {item['code']}"
                    product.slug = slugify(product.name)
                
                # Establecer el precio (sabemos que existe porque lo validamos arriba)
                product.price = float(item['price'])
                
                # Los demás campos son opcionales - manejar NaN correctamente
                if 'description' in item and item['description'] and not pd.isna(item['description']):
                    product.description = str(item['description'])
                
                # Google Merchant identifiers
                if 'gtin' in item and item['gtin'] and not pd.isna(item['gtin']):
                    product.gtin = str(item['gtin'])

                if 'mpn' in item and item['mpn'] and not pd.isna(item['mpn']):
                    product.mpn = str(item['mpn'])
                    
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
                        product.stock = int(float(item['stock']))  # Convertir a float primero, luego a int
                    except (ValueError, TypeError):
                        product.stock = 0  # Valor por defecto si hay error de conversión
                else:
                    # Valor predeterminado para stock si no se proporciona
                    product.stock = 0
                
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
                
                if 'brand' in item and item['brand'] and not pd.isna(item['brand']):
                    product.brand = str(item['brand'])
                
                if 'condition' in item and item['condition'] and not pd.isna(item['condition']):
                    product.condition = str(item['condition'])
                
                # Manejar imagen principal - solo si se proporciona
                if 'images' in item and item['images'] and not pd.isna(item['images']):
                    image_path = str(item['images']).strip()
                    
                    # Verificar si la imagen existe en el servidor
                    if os.path.exists(os.path.join('media', image_path)):
                        product.images = image_path
                    else:
                        # Registrar error pero continuar con la importación
                        image_errors.append(f"Imagen principal no encontrada para producto {item['code']}: {image_path}")
                
                # Intentar guardar el producto (podría fallar si faltan campos obligatorios del modelo)
                try:
                    product.save()
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
                        if os.path.exists(os.path.join('media', gallery_path)):
                            # Crear entrada en la galería
                            ProductGallery.objects.create(
                                product=product,
                                image=gallery_path
                            )
                        else:
                            # Registrar error pero continuar
                            image_errors.append(f"Imagen de galería no encontrada para producto {item['code']}: {gallery_path}")
                
                # Manejar subcategorías si se proporcionan
                if 'subcategories' in item and item['subcategories'] and not pd.isna(item['subcategories']):
                    subcats = str(item['subcategories']).split(',')
                    for subcat_name in subcats:
                        subcat_name = subcat_name.strip()
                        if subcat_name:  # Verificar que no esté vacío
                            try:
                                subcat = Category.objects.get(category_name=subcat_name)
                            except Category.DoesNotExist:
                                subcat = Category.objects.create(
                                    category_name=subcat_name,
                                    slug=slugify(subcat_name),
                                    parent=product.category
                                )
                            product.subcategories.add(subcat)
                
                success_count += 1
            except Exception as e:
                print(f"Error al importar producto {item.get('code', 'desconocido')}: {str(e)}")
                validation_errors.append(f"Error general para producto {item.get('code', 'desconocido')}: {str(e)}")
                failed_count += 1
        
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
                product_code = str(item['code'])
                
                # Verificar si el producto existe
                try:
                    product = Product.objects.get(code=product_code)
                    
                    # Convertir precio a float de manera segura
                    try:
                        new_price = float(item['price'])
                        product.price = new_price
                        product.save()
                        success_count += 1
                    except (ValueError, TypeError) as e:
                        validation_errors.append(f"Producto {product_code}: Error al convertir precio '{item['price']}' - {str(e)}")
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

admin.site.register(CarouselImage, CarouselImageAdmin)

# Si quieres ver las estadísticas de búsqueda en el admin
class ProductSearchAdmin(admin.ModelAdmin):
    list_display = ('product', 'search_count', 'user', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'user__email')
    readonly_fields = ('product', 'user', 'session_key', 'search_count', 'created_at', 'updated_at')

admin.site.register(ProductSearch, ProductSearchAdmin)

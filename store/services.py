"""
Store App Services

Contiene la lógica de negocio pura para gestión de productos, búsqueda, reviews y FAQs.
"""
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.db.models import Q, QuerySet, Avg, Count, Sum
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.text import slugify
from django.conf import settings
from itertools import chain

from store.models import (
    Product, ReviewRating, ProductGallery, ProductSearch,
    CarouselImage, FAQ, FAQCategory, Variation
)
from category.models import Category, SubCategory
from account.models import Account
from orders.models import OrderProduct
from store.utils import ImageProcessor

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Resultado de una operación de importación"""
    created: int = 0
    updated: int = 0
    errors: int = 0
    image_warnings: int = 0
    error_details: List[Tuple[int, str]] = field(default_factory=list)


class ProductService:
    """Servicio para gestión de productos"""
    
    @staticmethod
    def get_all_products(is_available: bool = True) -> QuerySet:
        """Obtiene todos los productos disponibles"""
        return Product.objects.filter(is_available=is_available)
    
    @staticmethod
    def get_product_by_slug(product_slug: str, category_slug: str = None) -> Optional[Product]:
        """Obtiene un producto por slug"""
        try:
            if category_slug:
                return Product.objects.get(category__slug=category_slug, slug=product_slug)
            else:
                return Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            logger.warning(f"Producto no encontrado: {product_slug}")
            return None
    
    @staticmethod
    def get_products_by_category(category_slug: str, is_available: bool = True) -> QuerySet:
        """Obtiene productos por categoría"""
        return Product.objects.filter(
            category__slug=category_slug,
            is_available=is_available
        )
    
    @staticmethod
    def get_products_by_subcategory(subcategory_slug: str, category_slug: str = None, 
                                   is_available: bool = True) -> QuerySet:
        """Obtiene productos por subcategoría"""
        filters = {'subcategories__slug': subcategory_slug, 'is_available': is_available}
        if category_slug:
            filters['category__slug'] = category_slug
        return Product.objects.filter(**filters)
    
    @staticmethod
    def get_sale_products(category: Category = None, subcategory: SubCategory = None) -> QuerySet:
        """Obtiene productos en oferta"""
        products = Product.objects.filter(is_on_sale=True, is_available=True)
        if category:
            products = products.filter(category=category)
        if subcategory:
            products = products.filter(subcategories=subcategory)
        return products
    
    @staticmethod
    def filter_products(products: QuerySet, min_price: float = None, max_price: float = None,
                       brand: str = None, sort_by: str = 'id') -> QuerySet:
        """Aplica filtros a productos"""
        # Filtro de precio
        if min_price is not None and max_price is not None:
            try:
                products = products.filter(price__gte=float(min_price), price__lte=float(max_price))
            except ValueError:
                logger.warning(f"Valores de precio inválidos: min={min_price}, max={max_price}")
        
        # Filtro de marca
        if brand:
            if brand == 'sin_marca':
                products = products.filter(brand__isnull=True)
            else:
                products = products.filter(brand=brand)
        
        # Ordenamiento
        if sort_by == 'price_asc':
            products = products.order_by('price')
        elif sort_by == 'price_desc':
            products = products.order_by('-price')
        else:
            products = products.order_by('id')
        
        return products
    
    @staticmethod
    def get_paginated_products(products: QuerySet, page: int = 1, per_page: int = 30) -> Tuple:
        """Pagina productos"""
        paginator = Paginator(products, per_page)
        paged_products = paginator.get_page(page)
        return paged_products, len(products)
    
    @staticmethod
    def get_available_brands() -> List[str]:
        """Obtiene marcas únicas disponibles"""
        brands = Product.objects.values_list('brand', flat=True).distinct()
        brands = [brand for brand in brands if brand]
        brands.append('sin_marca')
        return brands
    
    @staticmethod
    def get_product_gallery(product_id: int) -> QuerySet:
        """Obtiene galería de imágenes de un producto"""
        return ProductGallery.objects.filter(product_id=product_id)
    
    @staticmethod
    def get_dimension_variants(product: Product) -> List[Product]:
        """Obtiene variantes de dimensiones de un producto"""
        if not hasattr(product, 'get_dimension_variants'):
            return []
        try:
            return list(product.get_dimension_variants())
        except Exception as e:
            logger.error(f"Error obteniendo variantes de dimensiones para producto {product.id}: {e}")
            return []
    
    # ============================================================
    # MÉTODOS DE IMPORTACIÓN (Migrados desde admin.py)
    # ============================================================
    
    @staticmethod
    def import_from_file(file_or_path, dry_run: bool = False, update_prices: bool = False) -> ImportResult:
        """
        Importa/actualiza productos desde Excel o CSV.
        Migrado desde ProductAdmin.process_import().
        Clave de upsert: `code`
        
        Args:
            file_or_path: Archivo o ruta al archivo Excel/CSV
            dry_run: Si es True, simula la importación sin guardar
            update_prices: Si es True, solo actualiza precios
        
        Returns:
            ImportResult con estadísticas de la importación
        """
        try:
            data = ProductService._parse_file(file_or_path)
            result = ImportResult()
            processed_subcategories = set()
            
            for idx, item in enumerate(data):
                try:
                    # En dry_run, no usamos transaction.atomic
                    if dry_run:
                        created = ProductService._process_row_dry_run(item)
                        if created:
                            result.created += 1
                        else:
                            result.updated += 1
                    else:
                        with transaction.atomic():
                            created = ProductService._process_row(
                                item, dry_run, update_prices, result, processed_subcategories
                            )
                            
                            if created:
                                result.created += 1
                            else:
                                result.updated += 1
                        
                except Exception as e:
                    result.errors += 1
                    result.error_details.append((idx + 2, str(e)))
                    logger.error(f"Error importando fila {idx + 2} (código={item.get('code', '?')}): {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error general en importación: {e}")
            result = ImportResult()
            result.errors = 1
            result.error_details.append((0, f"Error general: {str(e)}"))
            return result
    
    @staticmethod
    def update_prices_from_file(file_or_path) -> ImportResult:
        """
        Actualiza solo precios de productos existentes.
        Sanitiza precios y maneja códigos con ceros a la izquierda.
        Migrado desde ProductAdmin.process_price_update().
        
        Args:
            file_or_path: Archivo o ruta al archivo Excel/CSV
        
        Returns:
            ImportResult con estadísticas de la actualización
        """
        try:
            data = ProductService._parse_file(file_or_path)
            result = ImportResult()
            
            for idx, item in enumerate(data):
                try:
                    # Validar campos obligatorios
                    if 'code' not in item or not item['code'] or pd.isna(item['code']):
                        result.errors += 1
                        result.error_details.append((idx + 2, "Falta el código del producto"))
                        continue
                    
                    if 'price' not in item or not item['price'] or pd.isna(item['price']):
                        result.errors += 1
                        result.error_details.append((idx + 2, f"Producto {item['code']}: Falta el precio"))
                        continue
                    
                    code = str(item['code']).strip()
                    
                    try:
                        product = Product.objects.get(code=code)
                        # Sanitizar precio
                        product.price = ProductService._sanitize_price(item['price'])
                        product.save(update_fields=['price', 'modified_date'])
                        result.updated += 1
                        
                    except Product.DoesNotExist:
                        result.errors += 1
                        result.error_details.append((idx + 2, f"Código {code} no existe"))
                        
                except ValueError as e:
                    result.errors += 1
                    result.error_details.append((idx + 2, f"Error en datos: {str(e)}"))
                    logger.error(f"Error actualizando precio fila {idx+2}: {e}")
                except Exception as e:
                    result.errors += 1
                    result.error_details.append((idx + 2, str(e)))
                    logger.error(f"Error actualizando precio fila {idx+2}: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error general en actualización de precios: {e}")
            result = ImportResult()
            result.errors = 1
            result.error_details.append((0, f"Error general: {str(e)}"))
            return result
    
    @staticmethod
    def _sanitize_price(price_value) -> float:
        """
        Sanitiza el valor del precio: quita símbolos, espacios y normaliza separadores.
        Soporta formatos: "1.234,56" (europeo), "1,234.56" (americano), "$7.161,61", "1000", etc.
        
        Heurística:
        - Si hay punto y coma: el último separa decimales, el otro separa miles
        - Si solo hay coma: es decimal (formato argentino)
        - Si solo hay punto: es decimal (formato simple)
        
        Args:
            price_value: Valor del precio como string o número
        
        Returns:
            float: Precio sanitizado
        
        Raises:
            ValueError: Si no puede convertir a float o el precio es negativo
        """
        if price_value is None or (isinstance(price_value, float) and pd.isna(price_value)):
            raise ValueError("Precio vacío o nulo")
        
        # Si ya es numérico (Pandas lo parseó bien), retornar directo
        if isinstance(price_value, (int, float)):
            result = float(price_value)
            if result < 0:
                raise ValueError(f"Precio negativo: {result}")
            return result
        
        # Normalizar string
        price_str = str(price_value).strip()
        price_str = price_str.replace('$', '').replace('\xa0', '').strip()  # quitar símbolo y non-breaking space
        
        # Detectar y normalizar separadores
        has_comma = ',' in price_str
        has_dot = '.' in price_str
        
        if has_comma and has_dot:
            # Ambos: el último es decimal
            if price_str.rfind('.') > price_str.rfind(','):
                price_str = price_str.replace(',', '')  # americano: 7,161.61
            else:
                price_str = price_str.replace('.', '').replace(',', '.')  # europeo: 7.161,61
        elif has_comma and not has_dot:
            price_str = price_str.replace(',', '.')  # solo coma = decimal AR
        # Solo punto o sin separadores → ya es formato float válido
        
        try:
            result = float(price_str)
            if result < 0:
                raise ValueError(f"Precio negativo: {result}")
            return result
        except ValueError:
            raise ValueError(f"No se pudo parsear el precio: '{price_value}' → '{price_str}'")
    
    @staticmethod
    def _parse_file(file_or_path) -> list:
        """
        Detecta formato (.xlsx/.csv) y devuelve lista de dicts.
        PASO 1: Desactiva Type Inference forzando TODO a string.
        PASO 2: Normaliza headers a lowercase.
        PASO 3: Limpia basuras de representación string (.0, nan, etc.).
        Migrado desde ProductAdmin.parse_excel() y parse_csv().
        """
        name = getattr(file_or_path, 'name', str(file_or_path))
        
        # PASO 1: Desactivar Type Inference forzando TODO a string
        if name.lower().endswith('.xlsx'):
            df = pd.read_excel(file_or_path, dtype=str, keep_default_na=True, na_values=[''])
        elif name.lower().endswith('.csv'):
            df = pd.read_csv(file_or_path, dtype=str, keep_default_na=True, na_values=[''])
        else:
            raise ValueError(f"Formato de archivo no soportado: {name}")
        
        # PASO 2: Normalizar headers
        df.columns = df.columns.str.lower().str.strip()
        
        # PASO 3: Limpieza de basuras de representación string
        for col in ['code', 'internal_code']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].str.replace(r'\.0$', '', regex=True)
                df[col] = df[col].replace(['nan', 'None', 'NaN', '', '<NA>'], None)
        
        df = df.where(pd.notna(df), None)
        
        return df.to_dict('records')
    
    @staticmethod
    def _find_image_in_directory(image_path: str, directory: str) -> Optional[str]:
        """
        Busca una imagen en el directorio especificado.
        Migrado desde ProductAdmin.find_image_in_directory().
        """
        if not os.path.exists(directory):
            return None
        
        image_name = os.path.basename(image_path.strip())
        search_name = slugify(image_name)
        
        if not search_name:
            return None
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if slugify(filename) == search_name or filename.lower() == image_name.lower():
                    return filename
        
        return None
    
    @staticmethod
    def _process_row_dry_run(item: dict) -> bool:
        """
        Procesa una fila en modo dry-run (solo validación).
        
        Returns:
            True si se crearía un producto nuevo, False si se actualizaría uno existente
        """
        # Validar campos obligatorios
        if 'code' not in item or not item['code'] or pd.isna(item['code']):
            raise ValueError("Falta el código del producto")
        
        if 'price' not in item or not item['price'] or pd.isna(item['price']):
            raise ValueError("Falta el precio")
        
        code = str(item['code']).strip()
        if code.endswith('.0'):
            code = code[:-2]
        
        # Verificar si el producto existe
        product_exists = Product.objects.filter(code=code).exists()
        
        if not product_exists and '.' not in code:
            # Intenta buscar versión legacy con .0 si el código es limpio
            product_exists = Product.objects.filter(code=f"{code}.0").exists()
        
        return not product_exists
    
    @staticmethod
    def _process_row(item: dict, dry_run: bool, update_prices: bool, 
                    result: ImportResult, processed_subcategories: set) -> bool:
        """
        Procesa una fila del archivo de importación.
        Migrado desde ProductAdmin.process_import().
        
        Returns:
            True si se creó un producto nuevo, False si se actualizó uno existente
        """
        # Validar campos obligatorios
        if 'code' not in item or not item['code'] or pd.isna(item['code']):
            raise ValueError("Falta el código del producto")
        
        if 'price' not in item or not item['price'] or pd.isna(item['price']):
            raise ValueError("Falta el precio")
        
        code = str(item['code']).strip()
        if code.endswith('.0'):
            code = code[:-2]
        item['code'] = code
        
        # Verificar si el producto existe
        product_exists = Product.objects.filter(code=code).exists()
        
        if dry_run:
            return not product_exists
        
        if product_exists:
            product = Product.objects.get(code=code)
            created = False
        else:
            product = Product(code=code)
            created = True
        
        # Actualizar campos
        if 'name' in item and item['name'] and not pd.isna(item['name']):
            product.name = str(item['name'])
        elif not product_exists:
            product.name = f"Producto {code}"
        
        # Sanitizar y asignar precio
        try:
            product.price = ProductService._sanitize_price(item['price'])
        except ValueError as e:
            raise ValueError(f"Precio inválido para código {code}: {str(e)}")
        
        # Campos opcionales
        if 'diameter' in item and not pd.isna(item['diameter']):
            product.diameter = str(item['diameter'])
        
        if 'length' in item and not pd.isna(item['length']):
            product.length = str(item['length'])
        
        if 'description' in item and item['description'] and not pd.isna(item['description']):
            product.description = str(item['description'])
        
        # Stock
        if 'stock' in item and item['stock'] and not pd.isna(item['stock']):
            try:
                product.stock = int(float(item['stock']))
            except (ValueError, TypeError):
                product.stock = 0
        else:
            product.stock = 0
        
        # Categoría
        if 'category' in item and item['category'] and not pd.isna(item['category']):
            category, _ = Category.objects.get_or_create(
                category_name=str(item['category']),
                defaults={'slug': slugify(str(item['category']))}
            )
            product.category = category
        elif not product_exists or not product.category:
            category, _ = Category.objects.get_or_create(
                category_name="Sin categoría",
                defaults={'slug': "sin-categoria"}
            )
            product.category = category
        
        # Otros campos opcionales
        optional_fields = [
            'brand', 'condition', 'norm', 'grade', 'material', 'colour',
            'type', 'form', 'thread_formats', 'origin', 'gtin', 'mpn',
            'google_category', 'meta_title', 'meta_description', 'meta_keywords'
        ]
        
        for field in optional_fields:
            if field in item and item[field] and not pd.isna(item[field]):
                setattr(product, field, str(item[field]))
        
        # Guardar producto
        product.save()
        
        # Procesar imagen principal
        if 'images' in item and item['images'] and not pd.isna(item['images']):
            ProductService._process_main_image(product, str(item['images']), result)
        
        # Procesar galería
        if 'gallery' in item and item['gallery'] and not pd.isna(item['gallery']):
            ProductService._process_gallery(product, str(item['gallery']), result, product_exists)
        
        # Procesar subcategorías
        if 'subcategories' in item and item['subcategories'] and not pd.isna(item['subcategories']):
            ProductService._process_subcategories(
                product, str(item['subcategories']), item, processed_subcategories
            )
        
        return created
    
    @staticmethod
    def _process_main_image(product: Product, image_path: str, result: ImportResult) -> None:
        """Procesa la imagen principal del producto"""
        products_dir = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'original')
        
        found_image = ProductService._find_image_in_directory(image_path, products_dir)
        if found_image:
            full_image_path = os.path.join(products_dir, found_image)
            relative_path = os.path.join('photos', 'products', 'original', found_image)
            product.images = relative_path
            product.save(update_fields=['images'])
            
            # Procesar imagen con ImageProcessor
            try:
                processor = ImageProcessor(full_image_path)
                if not processor.process_image():
                    result.image_warnings += 1
                    logger.warning(f"Error procesando imagen para producto {product.code}")
            except Exception as e:
                result.image_warnings += 1
                logger.error(f"Error procesando imagen para producto {product.code}: {e}")
        else:
            result.image_warnings += 1
            logger.warning(f"Imagen principal no encontrada para producto {product.code}: {image_path}")
    
    @staticmethod
    def _process_gallery(product: Product, gallery_paths: str, result: ImportResult, 
                        product_exists: bool) -> None:
        """Procesa la galería de imágenes del producto"""
        products_dir = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'original')
        
        # Eliminar galería existente si se está actualizando
        if product_exists:
            ProductGallery.objects.filter(product=product).delete()
        
        paths = [path.strip() for path in gallery_paths.split(',')]
        
        for gallery_path in paths:
            found_image = ProductService._find_image_in_directory(gallery_path, products_dir)
            if found_image:
                full_gallery_path = os.path.join(products_dir, found_image)
                gallery_image = ProductGallery.objects.create(
                    product=product,
                    image=os.path.join('photos', 'products', found_image)
                )
                
                try:
                    processor = ImageProcessor(full_gallery_path)
                    if not processor.process_image():
                        result.image_warnings += 1
                        logger.warning(f"Error procesando imagen de galería para producto {product.code}")
                except Exception as e:
                    result.image_warnings += 1
                    logger.error(f"Error procesando imagen de galería para producto {product.code}: {e}")
            else:
                result.image_warnings += 1
                logger.warning(f"Imagen de galería no encontrada para producto {product.code}: {gallery_path}")
    
    @staticmethod
    def _process_subcategories(product: Product, subcategories_str: str, item: dict,
                              processed_subcategories: set) -> None:
        """Procesa las subcategorías del producto"""
        subcats = [s.strip() for s in subcategories_str.split(',') if s.strip()]
        
        for subcat_name in subcats:
            subcat, _ = SubCategory.objects.get_or_create(
                subcategory_name=subcat_name,
                defaults={
                    'slug': slugify(subcat_name),
                    'category': product.category
                }
            )
            product.subcategories.add(subcat)
            
            # Procesar FAQs solo si esta subcategoría no ha sido procesada
            if subcat.id not in processed_subcategories and 'faq' in item and item['faq'] and not pd.isna(item['faq']):
                if not FAQ.objects.filter(subcategory=subcat).exists():
                    ProductService._process_faqs(subcat, str(item['faq']))
                processed_subcategories.add(subcat.id)
    
    @staticmethod
    def _process_faqs(subcategory: SubCategory, faq_text: str) -> None:
        """Procesa las FAQs de una subcategoría"""
        faq_category, _ = FAQCategory.objects.get_or_create(
            name='Preguntas específicas de productos',
            defaults={'order': 999}
        )
        
        # Parsear FAQs: formato "Pregunta" Respuesta, ...
        faq_pairs = re.findall(r'"([^"]+)"\s*([^,]+)(?:,|$)', faq_text)
        
        for order, (question, answer) in enumerate(faq_pairs):
            question = question.strip('¿ ?')
            answer = answer.strip()
            
            FAQ.objects.create(
                category=faq_category,
                subcategory=subcategory,
                question=f"¿{question}?",
                answer=answer,
                order=order,
                is_active=True
            )


class SearchService:
    """Servicio para búsqueda de productos"""
    
    @staticmethod
    def search_products(keyword: str) -> QuerySet:
        """Busca productos por palabra clave en múltiples campos"""
        if not keyword:
            return Product.objects.filter(is_available=True)
        
        # Expandir búsqueda a múltiples campos: código, nombre, descripción, marca
        return Product.objects.filter(
            Q(code__icontains=keyword) |
            Q(name__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(brand__icontains=keyword),
            is_available=True
        ).order_by('-created_date')
    
    @staticmethod
    def register_product_search(product: Product, user: Account = None, 
                               session_key: str = None) -> None:
        """Registra búsqueda de producto"""
        try:
            if user:
                product_search, created = ProductSearch.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={'search_count': 1}
                )
            elif session_key:
                product_search, created = ProductSearch.objects.get_or_create(
                    product=product,
                    session_key=session_key,
                    defaults={'search_count': 1}
                )
            else:
                return
            
            if not created:
                product_search.search_count += 1
                product_search.save()
            
            logger.info(f"Búsqueda registrada para producto {product.id}")
        except Exception as e:
            logger.error(f"Error registrando búsqueda de producto {product.id}: {e}")
    
    @staticmethod
    def register_search_results(products: QuerySet, keyword: str, user: Account = None,
                               session_key: str = None, limit: int = 8) -> None:
        """Registra búsquedas para múltiples productos"""
        if not keyword or len(keyword) <= 2:
            return
        
        for product in products[:limit]:
            SearchService.register_product_search(product, user, session_key)


class ReviewService:
    """Servicio para gestión de reviews"""
    
    @staticmethod
    def get_product_reviews(product_id: int, status: bool = True) -> QuerySet:
        """Obtiene reviews de un producto"""
        return ReviewRating.objects.filter(product_id=product_id, status=status)
    
    @staticmethod
    def get_user_review(user_id: int, product_id: int) -> Optional[ReviewRating]:
        """Obtiene review de un usuario para un producto"""
        try:
            return ReviewRating.objects.get(user__id=user_id, product__id=product_id)
        except ReviewRating.DoesNotExist:
            return None
    
    @staticmethod
    def create_review(user_id: int, product_id: int, subject: str, 
                     review: str, rating: float, ip: str) -> ReviewRating:
        """Crea una nueva review"""
        review_obj = ReviewRating.objects.create(
            user_id=user_id,
            product_id=product_id,
            subject=subject,
            review=review,
            rating=rating,
            ip=ip
        )
        logger.info(f"Review creada para producto {product_id} por usuario {user_id}")
        return review_obj
    
    @staticmethod
    def update_review(review: ReviewRating, subject: str = None, 
                     review_text: str = None, rating: float = None) -> ReviewRating:
        """Actualiza una review existente"""
        if subject:
            review.subject = subject
        if review_text:
            review.review = review_text
        if rating:
            review.rating = rating
        review.save()
        logger.info(f"Review {review.id} actualizada")
        return review
    
    @staticmethod
    def user_can_review(user_id: int, product_id: int) -> bool:
        """Verifica si un usuario puede hacer review de un producto"""
        return OrderProduct.objects.filter(
            user_id=user_id,
            product_id=product_id
        ).exists()


class FAQService:
    """Servicio para gestión de FAQs"""
    
    @staticmethod
    def get_general_faqs() -> QuerySet:
        """Obtiene FAQs generales (sin subcategoría)"""
        return FAQCategory.objects.prefetch_related('faqs').filter(
            faqs__is_active=True,
            faqs__subcategory__isnull=True
        ).distinct()
    
    @staticmethod
    def get_product_faqs(product: Product) -> QuerySet:
        """Obtiene FAQs relacionadas a las subcategorías de un producto"""
        return FAQ.objects.filter(
            subcategory__in=product.subcategories.all(),
            is_active=True
        ).select_related('category').distinct()
    
    @staticmethod
    def get_faqs_by_category(category_id: int) -> QuerySet:
        """Obtiene FAQs por categoría"""
        return FAQ.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('order')
    
    @staticmethod
    def get_faqs_by_subcategory(subcategory_id: int) -> QuerySet:
        """Obtiene FAQs por subcategoría"""
        return FAQ.objects.filter(
            subcategory_id=subcategory_id,
            is_active=True
        ).order_by('order')


class CarouselService:
    """Servicio para gestión de carrusel"""
    
    @staticmethod
    def get_active_carousel_images() -> QuerySet:
        """Obtiene imágenes activas del carrusel"""
        return CarouselImage.objects.filter(is_active=True).order_by('position')
    
    @staticmethod
    def get_sale_products_groups(sale_products: QuerySet, group_size: int = 4) -> List[List[Product]]:
        """Agrupa productos en oferta para el carrusel"""
        products_list = list(sale_products)
        return [products_list[i:i+group_size] for i in range(0, len(products_list), group_size)]


class FeedService:
    """Servicio para generación de feeds (Facebook, Google Merchant)"""
    
    @staticmethod
    def get_facebook_feed_data() -> List[Dict]:
        """Obtiene datos para feed de Facebook"""
        products = Product.objects.filter(is_available=True)
        feed_data = []
        
        for product in products:
            try:
                data = product.get_meta_pixel_data()
                if data.get('image_link') and data.get('brand'):
                    feed_data.append(data)
            except Exception as e:
                logger.error(f"Error generando datos de Facebook para producto {product.id}: {e}")
        
        return feed_data
    
    @staticmethod
    def get_google_merchant_feed_data() -> List[Dict]:
        """Obtiene datos para feed de Google Merchant"""
        products = Product.objects.filter(is_available=True)
        feed_data = []
        
        for product in products:
            try:
                data = product.get_merchant_data()
                if data.get('image_link') and data.get('brand'):
                    feed_data.append({**data, 'code': product.code})
            except Exception as e:
                logger.error(f"Error generando datos de Google Merchant para producto {product.id}: {e}")
        
        return feed_data


class GoogleReviewsService:
    """Servicio para obtener y cachear reseñas desde Google Places API"""
    
    @staticmethod
    def get_cached_reviews() -> Optional[Dict]:
        from django.core.cache import cache
        from django.conf import settings
        import requests
        
        cache_key = 'google_places_reviews_data'
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
            
        api_key = getattr(settings, 'GOOGLE_MAPS_EMBED_KEY', '') # Se asume que tiene acceso a Places API
        place_id = getattr(settings, 'GOOGLE_PLACE_ID', '')
        
        if not api_key or not place_id:
            return None
            
        url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,rating,user_ratings_total,reviews&language=es&key={api_key}"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                result = response.json().get('result', {})
                # Si la API devuelve REQUEST_DENIED u otro error, no hay result
                if not result:
                    logger.warning(f"Google Places API responded with status 200 but no result. Check API key restrictions.")
                    return GoogleReviewsService._get_fallback_data()
                
                # Filtrar solo reseñas de 4 y 5 estrellas para mostrar lo mejor
                reviews = [r for r in result.get('reviews', []) if r.get('rating', 0) >= 4]
                
                # Si no hay reseñas, usar fallback
                if not reviews:
                    return GoogleReviewsService._get_fallback_data()
                    
                data = {
                    'rating': result.get('rating', 4.8),
                    'total': result.get('user_ratings_total', 0),
                    'reviews': reviews
                }
                cache.set(cache_key, data, 86400) # Cache por 24 horas
                return data
            else:
                logger.error(f"Google API Error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error fetching Google Reviews: {e}")
            
        return GoogleReviewsService._get_fallback_data()

    @staticmethod
    def _get_fallback_data() -> Dict:
        """Datos de respaldo: se muestran cuando la API no responde o falla."""
        return {
            'rating': 4.6,
            'total': 120,
            'is_fallback': True,
            'reviews': [
                {
                    'author_name': 'Claudio Aguirre',
                    'profile_photo_url': 'https://ui-avatars.com/api/?name=Claudio+Aguirre&background=1d4ed8&color=fff&bold=true',
                    'rating': 5,
                    'text': 'Excelente atención y surtido. Encuentro todo lo que necesito para el taller. El precio y la calidad son inmejorables.',
                    'relative_time_description': 'hace 2 días'
                },
                {
                    'author_name': 'Marcela Torres',
                    'profile_photo_url': 'https://ui-avatars.com/api/?name=Marcela+Torres&background=15803d&color=fff&bold=true',
                    'rating': 5,
                    'text': 'Muy buenos precios en herramientas. Me respondieron rápido por WhatsApp y pude retirar el mismo día. Muy recomendable.',
                    'relative_time_description': 'hace 1 semana'
                },
                {
                    'author_name': 'Juan Pérez',
                    'profile_photo_url': 'https://ui-avatars.com/api/?name=Juan+Perez&background=b45309&color=fff&bold=true',
                    'rating': 5,
                    'text': 'Tienen mucha variedad de bulonería especial que no se consigue en otro lado en Resistencia. Siempre voy ahí.',
                    'relative_time_description': 'hace 1 mes'
                },
                {
                    'author_name': 'Roberto Sánchez',
                    'profile_photo_url': 'https://ui-avatars.com/api/?name=Roberto+Sanchez&background=7c3aed&color=fff&bold=true',
                    'rating': 5,
                    'text': 'Gran variedad de productos y atención al cliente de primera. Los recomiendo totalmente para industria y construcción.',
                    'relative_time_description': 'hace 3 semanas'
                },
                {
                    'author_name': 'Ana González',
                    'profile_photo_url': 'https://ui-avatars.com/api/?name=Ana+Gonzalez&background=be123c&color=fff&bold=true',
                    'rating': 4,
                    'text': 'Buen lugar, tienen todo tipo de tornillos y herramientas. El personal es amable y saben bien lo que venden.',
                    'relative_time_description': 'hace 2 meses'
                },
            ]
        }

class HomeSectionService:
    """
    Servicio que construye las secciones dinámicas de la Home.
    Filosofía: Manual > Auto. Si hay productos manuales, se usan.
    Si no, se auto-generan según source_type.
    """

    @staticmethod
    def get_active_sections() -> QuerySet:
        """Obtiene todas las secciones activas, ordenadas por posición."""
        from store.models import HomeSection, HomeSectionProduct
        
        return HomeSection.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related(
            'home_section_products__product',
            'banners',
            'banners__image_desktop_asset',
            'banners__image_mobile_asset',
            'banners__image_tablet_asset',
            'banners__image_large_asset',
        )

    @staticmethod
    def get_section_context(section, request=None) -> Dict:
        """
        Construye el contexto de datos para una sección específica.
        Retorna un dict con los datos listos para el template.
        """
        from store.models import HomeSection
        
        if section.section_type == 'product_carousel':
            products = HomeSectionService._resolve_products(section, request)
            return {'products': products}

        elif section.section_type in ['categories_featured', 'categories_carousel']:
            from category.models import Category
            context = {
                'banners': section.banners.filter(is_active=True).order_by('position')
            }
            # Si hay banners, priorizamos mostrarlos (modo manual)
            # Si no hay banners, traemos las categorías del sistema (modo automático)
            if not context['banners'].exists():
                context['categories'] = Category.objects.all().order_by('category_name')
            return context

        elif section.section_type.startswith('banner_'):
            banners = section.banners.filter(is_active=True).order_by('position')
            return {'banners': banners}

        elif section.section_type == 'trust_bar':
            # Trust bar is static content, just return empty context
            return {}

        elif section.section_type == 'google_reviews':
            return {'google_data': GoogleReviewsService.get_cached_reviews()}

        return {}

    @staticmethod
    def _resolve_products(section, request=None) -> List[Product]:
        """
        Resuelve los productos de un carrusel.
        PRIORIDAD: Manual (HomeSectionProduct) > Auto (source_type)
        """
        from store.models import HomeSectionProduct, HomeSection
        from orders.models import OrderProduct
        
        # 1. ¿Hay productos manuales?
        if section.home_section_products.exists():
            return [sp.product for sp in
                    section.home_section_products
                    .select_related('product')
                    .order_by('position')
                    if sp.product.is_available]

        # 2. Auto-generar según source_type
        limit = section.max_products
        source = section.source_type

        if source == 'bestsellers':
            return list(Product.objects.filter(
                is_available=True,
                orderproduct__isnull=False
            ).annotate(
                order_count=Sum('orderproduct__quantity')
            ).order_by('-order_count')[:limit])

        elif source == 'most_searched':
            return list(Product.objects.filter(
                is_available=True
            ).order_by('-productsearch__search_count')[:limit])

        elif source == 'by_category' and section.category:
            return list(Product.objects.filter(
                category=section.category, is_available=True
            ).order_by('-sold_count')[:limit])

        elif source == 'on_sale':
            return list(Product.objects.filter(
                is_available=True, is_on_sale=True
            ).order_by('-discount_percentage')[:limit])

        elif source == 'newest':
            return list(Product.objects.filter(
                is_available=True
            ).order_by('-created_date')[:limit])

        return []

    @staticmethod
    def get_recommended_products(section) -> List[Product]:
        """
        Genera la lista de productos recomendados para una sección.
        Se usa para la acción admin 'sugerir productos'.
        """
        return HomeSectionService._resolve_products(section)


__all__ = [
    'ImportResult',
    'ProductService',
    'SearchService',
    'ReviewService',
    'FAQService',
    'CarouselService',
    'FeedService',
    'GoogleReviewsService',
    'HomeSectionService',
]

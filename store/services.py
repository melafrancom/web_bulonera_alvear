"""
Store App Services

Contiene la lógica de negocio pura para gestión de productos, búsqueda, reviews y FAQs.
"""
import hashlib
import logging
import os
import io
import re
import uuid
import zlib
import json
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import pandas as pd
from django.db.models import Q, QuerySet, Avg, Count, Sum, Case, When, Value, IntegerField, F
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from itertools import chain

from store.models import (
    Product, ReviewRating, ProductGallery, ProductSearch,
    SearchQuery, SearchQueryDaily, CarouselImage, FAQ, FAQCategory, Variation
)
from store.relation_utils import (
    COMPATIBLE_THREAD_FAMILIES,
    normalize_thread_format,
    parse_diameter_and_pitch,
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
    tags_created: List[str] = field(default_factory=list)



class PricingService:
    """
    Servicio de cálculo y desglose de precios conforme a la Resolución 4/2025 (Secretaría de Comercio).
    
    # REGLA: Exige exhibir el precio final con IVA y, en tipografía menor, el precio neto sin impuestos
    # nacionales indirectos. Si un producto no tiene alícuota explícita, se aplica la tasa general (21.00%).
    """
    DEFAULT_TAX_RATE = Decimal('21.00')

    @classmethod
    def calculate_net_price(cls, gross_amount, tax_rate=None) -> Decimal:
        """
        Calcula el precio neto sin impuestos indirectos nacionales a partir del precio final.
        Fórmula: Precio Neto = Precio Final / (1 + (Alícuota / 100))
        """
        if gross_amount is None:
            return Decimal('0.00')
        try:
            d_gross = Decimal(str(gross_amount))
        except (ValueError, TypeError, InvalidOperation):
            return Decimal('0.00')

        if d_gross <= Decimal('0.00'):
            return Decimal('0.00')

        if tax_rate is not None:
            try:
                d_rate = Decimal(str(tax_rate))
            except (ValueError, TypeError, InvalidOperation):
                d_rate = cls.DEFAULT_TAX_RATE
        else:
            d_rate = cls.DEFAULT_TAX_RATE

        divisor = Decimal('1.00') + (d_rate / Decimal('100.00'))
        return (d_gross / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class ProductService:
    """Servicio para gestión de productos"""
    IMPORT_CHUNK_SIZE: int = 250
    PRICES_CHUNK_SIZE: int = 500
    BULK_UPLOAD_CACHE_TIMEOUT: int = 3600  # 1 hora
    
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
                       brand: str = None, sort_by: str = 'id', tags: list = None) -> QuerySet:
        """Aplica filtros a productos"""
        # Filtro por tags (semántica AND sin ensuciar los joins principales)
        if tags:
            for tag in tags:
                if str(tag).isdigit():
                    subquery = Product.objects.filter(tags__id=int(tag)).values('pk')
                else:
                    subquery = Product.objects.filter(tags__slug=tag).values('pk')
                products = products.filter(pk__in=subquery)
                
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
        """Pagina productos usando paginator.count para evitar materializar QuerySets completos."""
        paginator = Paginator(products, per_page)
        paged_products = paginator.get_page(page)
        return paged_products, paginator.count
    
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
        return ProductGallery.objects.filter(product_id=product_id).select_related('image_asset')
    
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

    # Especificación canónica de las 33 columnas del importador masivo
    IMPORT_TEMPLATE_COLUMNS: List[Dict[str, any]] = [
        {
            'name': 'code',
            'required': True,
            'group': 'required',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Código único de producto (SKU o código interno del ERP). Preserva ceros a la izquierda.',
            'sample_1': '00100100025',
            'sample_2': 'MAQ-TAL-001',
            'sample_3': '00100400015',
        },
        {
            'name': 'price',
            'required': True,
            'group': 'required',
            'format': '#,##0.00',
            'type_desc': 'Decimal',
            'rule': 'Precio final de venta con IVA incluido. Admite formato con punto o coma decimal.',
            'sample_1': '1250.50',
            'sample_2': '185000.00',
            'sample_3': '340.00',
        },
        {
            'name': 'name',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Nombre del producto. Si se omite, se autogenera como "Producto {code}". Si incluye diámetro y largo se concatenan.',
            'sample_1': 'Bulón Cabeza Hexagonal G2 UNC Zincado',
            'sample_2': 'Taladro Percutor Inalámbrico 18V Brushless',
            'sample_3': 'Arandela Grover Inoxidable A2',
        },
        {
            'name': 'diameter',
            'required': False,
            'group': 'tech',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Diámetro o medida nominal (ej. 1/4", 3/8", M8). Se formatea como texto para evitar conversión a fechas en Excel.',
            'sample_1': '1/4"',
            'sample_2': '',
            'sample_3': '5/16"',
        },
        {
            'name': 'length',
            'required': False,
            'group': 'tech',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Longitud o largo del producto (ej. 1-1/2", 50mm, 2"). Se formatea como texto para evitar conversión a fechas.',
            'sample_1': '1-1/2"',
            'sample_2': '',
            'sample_3': '',
        },
        {
            'name': 'description',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto largo',
            'rule': 'Descripción detallada del producto para la ficha técnica y tienda online.',
            'sample_1': 'Bulón cabeza hexagonal rosca gruesa zincado brillante para uso general en herrería y carpintería.',
            'sample_2': 'Taladro percutor a batería 18V motor sin carbones con 2 baterías de 4Ah y maletín.',
            'sample_3': 'Arandela de presión Grover en acero inoxidable AISI 304 calidad náutica e industrial.',
        },
        {
            'name': 'stock',
            'required': False,
            'group': 'catalog',
            'format': '#,##0',
            'type_desc': 'Entero',
            'rule': 'Stock físico disponible. Valor por defecto: 0.',
            'sample_1': '500',
            'sample_2': '15',
            'sample_3': '2000',
        },
        {
            'name': 'category',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Categoría principal. Si no existe, el sistema la crea automáticamente. Por defecto: "Sin categoría".',
            'sample_1': 'Bulonería',
            'sample_2': 'Herramientas',
            'sample_3': 'Bulonería',
        },
        {
            'name': 'subcategories',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto (separado por comas)',
            'rule': 'Subcategorías asociadas separadas por comas. Si no existen, se crean vinculadas a la categoría.',
            'sample_1': 'Tornillos y Bulones, Hexagonales',
            'sample_2': 'Máquinas Eléctricas, Herramientas a Batería',
            'sample_3': 'Arandelas, Arandelas de Presión',
        },
        {
            'name': 'related_subcategories',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto (separado por comas)',
            'rule': 'Subcategorías relacionadas existentes separadas por comas (alias: ProductRelation). Vacío conserva; "-" limpia.',
            'sample_1': 'Tuercas Hexagonales, Arandelas Planas',
            'sample_2': 'Mechas Widia',
            'sample_3': '',
        },
        {
            'name': 'diameter_relation',
            'required': False,
            'group': 'tech',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Diámetro(s) a buscar en las subcategorías relacionadas (separados por coma, ej. 6 u 8, 10). Vacío aplica Opción B; "-" limpia.',
            'sample_1': '1/4',
            'sample_2': '',
            'sample_3': '',
        },
        {
            'name': 'thread_formats_relation',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Formato o paso de rosca a filtrar en complementos con rosca (ej. MA, UNC, P 1.0). No excluye arandelas. "-" limpia.',
            'sample_1': 'UNC',
            'sample_2': '',
            'sample_3': '',
        },
        {
            'name': 'tags',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto (separado por comas)',
            'rule': 'Etiquetas comerciales transversales (ProductTag) separadas por comas. Se crean automáticamente si no existen.',
            'sample_1': 'Zincado, Fijaciones, Estándar',
            'sample_2': 'Inalámbrico, Profesional, 18V, Oferta',
            'sample_3': 'Inoxidable, Grover, Náutico, Industria',
        },
        {
            'name': 'tax_rate',
            'required': False,
            'group': 'catalog',
            'format': '0.00',
            'type_desc': 'Decimal / Lista',
            'rule': 'Alícuota IVA (%) según Resolución 4/2025. Opciones: 21.00, 10.50, 0.00. Si se omite, se aplica 21.00% por defecto.',
            'sample_1': '21.00',
            'sample_2': '10.50',
            'sample_3': '21.00',
        },
        {
            'name': 'brand',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Marca o fabricante del producto.',
            'sample_1': 'Bulonera Alvear',
            'sample_2': 'DeWalt',
            'sample_3': 'Bulonera Alvear',
        },
        {
            'name': 'condition',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Lista (new/used/refurbished)',
            'rule': 'Condición del producto: new (Nuevo), used (Usado), refurbished (Reacondicionado). Por defecto: new.',
            'sample_1': 'new',
            'sample_2': 'new',
            'sample_3': 'new',
        },
        {
            'name': 'images',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Nombre de archivo',
            'rule': 'Nombre del archivo de imagen principal en media/photos/products/original/ (ej. tornillo.jpg).',
            'sample_1': 'bulon-hexagonal-g2-zincado.jpg',
            'sample_2': 'taladro-dewalt-18v.jpg',
            'sample_3': 'arandela-grover-inox.jpg',
        },
        {
            'name': 'gallery',
            'required': False,
            'group': 'catalog',
            'format': 'General',
            'type_desc': 'Nombres separados por coma',
            'rule': 'Imágenes secundarias en media/photos/products/original/ separadas por comas sin espacios.',
            'sample_1': 'bulon-hex-detalle.jpg',
            'sample_2': 'taladro-dewalt-kit.jpg,taladro-dewalt-maletin.jpg',
            'sample_3': '',
        },
        {
            'name': 'norm',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Norma técnica industrial (ej. DIN 933, SAE J429, ISO 4017).',
            'sample_1': 'SAE J429',
            'sample_2': '',
            'sample_3': 'DIN 127 B',
        },
        {
            'name': 'grade',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Grado o dureza del material (ej. Grado 2, Grado 5, 8.8, 10.9, AISI 304).',
            'sample_1': 'Grado 2',
            'sample_2': '',
            'sample_3': 'AISI 304 / A2',
        },
        {
            'name': 'material',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Material de composición (ej. Acero al carbono, Acero Inoxidable, Bronce).',
            'sample_1': 'Acero al carbono',
            'sample_2': 'Poliamida y engranajes metálicos',
            'sample_3': 'Acero Inoxidable A2-70',
        },
        {
            'name': 'colour',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Color o terminación superficial (ej. Zincado azul, Negro pavonado, Amarillo/Negro).',
            'sample_1': 'Zincado brillante',
            'sample_2': 'Amarillo / Negro',
            'sample_3': 'Inox natural',
        },
        {
            'name': 'type',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Tipo de sistema de rosca o herramienta (ej. Pulgadas UNC, Métrico, Inalámbrico).',
            'sample_1': 'Pulgadas UNC',
            'sample_2': 'Inalámbrico',
            'sample_3': 'Pulgadas',
        },
        {
            'name': 'form',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Forma geométrica del producto (ej. Cabeza hexagonal, Cilíndrica, Grower helicoidal).',
            'sample_1': 'Cabeza hexagonal',
            'sample_2': 'Pistola ergonómica',
            'sample_3': 'Grower helicoidal',
        },
        {
            'name': 'thread_formats',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Paso o formato de rosca / mandril (ej. Paso grueso, Fina, Mandril 13mm).',
            'sample_1': 'Paso grueso (UNC)',
            'sample_2': 'Mandril autoajustable 13mm',
            'sample_3': '',
        },
        {
            'name': 'origin',
            'required': False,
            'group': 'tech',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'País de origen o fabricación.',
            'sample_1': 'Argentina',
            'sample_2': 'Brasil',
            'sample_3': 'Argentina',
        },
        {
            'name': 'gtin',
            'required': False,
            'group': 'seo',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Código universal de producto (EAN-13, UPC). Preserva ceros iniciales.',
            'sample_1': '7791234567890',
            'sample_2': '885911234567',
            'sample_3': '7791234567999',
        },
        {
            'name': 'mpn',
            'required': False,
            'group': 'seo',
            'format': '@',
            'type_desc': 'Texto',
            'rule': 'Número de parte del fabricante (Manufacturer Part Number).',
            'sample_1': 'BH-G2-14112',
            'sample_2': 'DCD796D2',
            'sample_3': 'AG-INOX-516',
        },
        {
            'name': 'google_category',
            'required': False,
            'group': 'seo',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Taxonomía de Google Merchant Feed (ej. Hardware > Fasteners > Bolts).',
            'sample_1': 'Hardware > Fasteners > Bolts',
            'sample_2': 'Hardware > Tools > Drills',
            'sample_3': 'Hardware > Fasteners > Washers',
        },
        {
            'name': 'faq',
            'required': False,
            'group': 'seo',
            'format': 'General',
            'type_desc': 'Texto estructurado',
            'rule': 'Preguntas y respuestas frecuentes vinculadas a la subcategoría en formato: "¿Pregunta?" Respuesta, "¿Pregunta 2?" Respuesta 2',
            'sample_1': '"¿Viene con tuerca?" No, las tuercas se adquieren por separado',
            'sample_2': '"¿Incluye batería y cargador?" Sí, 2 baterías y maletín',
            'sample_3': '"¿Es resistente al agua?" Sí, apto náutica y exteriores',
        },
        {
            'name': 'meta_title',
            'required': False,
            'group': 'seo',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Meta título SEO personalizado (máx 70 caracteres). Si está vacío se autogenera en save().',
            'sample_1': 'Bulón Hexagonal G2 1/4 x 1-1/2 | Bulonera Alvear',
            'sample_2': 'Taladro Percutor DeWalt 18V Brushless | Bulonera Alvear',
            'sample_3': 'Arandela Grover Inoxidable 5/16 | Bulonera Alvear',
        },
        {
            'name': 'meta_description',
            'required': False,
            'group': 'seo',
            'format': 'General',
            'type_desc': 'Texto',
            'rule': 'Meta descripción SEO personalizada (máx 160 caracteres). Si está vacía se autogenera en save().',
            'sample_1': 'Bulón cabeza hexagonal rosca gruesa zincado. Stock en Resistencia Chaco.',
            'sample_2': 'Taladro percutor a batería DeWalt 18V con 2 baterías. Garantía oficial.',
            'sample_3': 'Arandelas de presión Grover de acero inoxidable AISI 304 calidad A2.',
        },
        {
            'name': 'meta_keywords',
            'required': False,
            'group': 'seo',
            'format': 'General',
            'type_desc': 'Texto (separado por comas)',
            'rule': 'Palabras clave SEO separadas por comas. Si está vacío se autogenera a partir del nombre.',
            'sample_1': 'bulon, hexagonal, zincado, resistencia',
            'sample_2': 'taladro, percutor, dewalt, 18v',
            'sample_3': 'arandela, grover, inox, aisi 304',
        },
    ]

    @staticmethod
    def _get_excel_styles() -> Dict[str, object]:
        """Retorna la paleta de estilos corporativos compartida entre plantillas y exportaciones Excel."""
        return {
            'fill_green': PatternFill(start_color="166534", end_color="166534", fill_type="solid"),
            'fill_navy': PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid"),
            'fill_slate': PatternFill(start_color="334155", end_color="334155", fill_type="solid"),
            'fill_blue': PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid"),
            'fill_light_gray': PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
            'font_header': Font(name="Calibri", size=11, bold=True, color="FFFFFF"),
            'font_title': Font(name="Calibri", size=14, bold=True, color="1B3A5C"),
            'font_subtitle': Font(name="Calibri", size=11, italic=True, color="475569"),
            'font_bold': Font(name="Calibri", size=11, bold=True, color="1E293B"),
            'font_regular': Font(name="Calibri", size=11, color="334155"),
            'align_center': Alignment(horizontal="center", vertical="center"),
            'align_left': Alignment(horizontal="left", vertical="center"),
            'align_wrap': Alignment(horizontal="left", vertical="top", wrap_text=True),
            'border_thin': Border(
                left=Side(style='thin', color='CBD5E1'),
                right=Side(style='thin', color='CBD5E1'),
                top=Side(style='thin', color='CBD5E1'),
                bottom=Side(style='thin', color='CBD5E1'),
            ),
        }

    @staticmethod
    def _create_write_only_cell(
        ws,
        value,
        font=None,
        fill=None,
        alignment=None,
        border=None,
        number_format: Optional[str] = None,
    ) -> WriteOnlyCell:
        """
        Construye una celda compatible con WriteOnlyWorksheet sanitizando caracteres XML
        ilegales y protegiendo strings que comiencen con operadores de fórmula.
        """
        if isinstance(value, str):
            value = ILLEGAL_CHARACTERS_RE.sub('', value)

        cell = WriteOnlyCell(ws, value=value)
        # REGLA: Forzar data_type='s' cuando el texto inicia con operadores interpretables como
        # fórmula ('=', '+', '-', '@') o caracteres de control iniciales para prevenir Formula Injection (CWE-1236).
        if isinstance(value, str) and (
            value.startswith(('=', '+', '-', '@', '\t', '\r', '\n'))
            or value.lstrip().startswith(('=', '+', '-', '@'))
        ):
            cell.data_type = 's'
        if font is not None:
            cell.font = font
        if fill is not None:
            cell.fill = fill
        if alignment is not None:
            cell.alignment = alignment
        if border is not None:
            cell.border = border
        if number_format is not None:
            cell.number_format = number_format
        return cell

    @classmethod
    def _sanitize_export_scalar(cls, ws, value, force_text: bool = False):
        """
        Normaliza valores de celda para exportación en streaming: limpia caracteres XML
        inválidos y envuelve en WriteOnlyCell cuando se exige formato texto o tipo literal.
        """
        if value is None:
            clean_val = ''
        elif isinstance(value, str):
            clean_val = ILLEGAL_CHARACTERS_RE.sub('', value)
        else:
            clean_val = value

        if force_text:
            str_val = str(clean_val) if clean_val != '' else ''
            return cls._create_write_only_cell(ws, str_val, number_format='@')

        if isinstance(clean_val, str) and clean_val.startswith(('=', '+', '-', '@')):
            return cls._create_write_only_cell(ws, clean_val)

        return clean_val

    @classmethod
    def _append_styled_row(
        cls,
        ws,
        row_idx: int,
        cells_spec: List[Tuple[object, Dict[str, object]]],
        write_only: bool,
        height: Optional[int] = None,
    ) -> int:
        """Agrega una fila estilizada de manera uniforme en hojas normales o write-only."""
        if write_only:
            if height is not None:
                ws.row_dimensions[row_idx].height = height
            if not cells_spec:
                ws.append([])
            else:
                ws.append([
                    cls._create_write_only_cell(ws, val, **style_kwargs)
                    for val, style_kwargs in cells_spec
                ])
        else:
            if height is not None:
                ws.row_dimensions[row_idx].height = height
            if not cells_spec:
                ws.append([])
            else:
                for c_idx, (val, style_kwargs) in enumerate(cells_spec, 1):
                    cell = ws.cell(row=row_idx, column=c_idx, value=val)
                    for attr, attr_val in style_kwargs.items():
                        setattr(cell, attr, attr_val)
        return row_idx + 1

    @classmethod
    def _configure_products_sheet(
        cls,
        ws,
        styles: Dict[str, object],
        write_only: bool = False,
        validation_max_row: int = 2000,
    ) -> None:
        """
        Configura dimensiones, congelamiento de encabezado, validaciones desplegables y fila
        de encabezados de las 33 columnas canónicas en la hoja 'Productos'.
        """
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 28

        header_specs = []
        for col_idx, col_spec in enumerate(cls.IMPORT_TEMPLATE_COLUMNS, 1):
            h_name = col_spec['name']
            grp = col_spec['group']
            if grp == 'required':
                header_fill = styles['fill_green']
            elif grp == 'catalog':
                header_fill = styles['fill_navy']
            elif grp == 'tech':
                header_fill = styles['fill_slate']
            else:
                header_fill = styles['fill_blue']

            col_letter = get_column_letter(col_idx)
            if col_spec.get('format') == '@':
                ws.column_dimensions[col_letter].number_format = '@'
            ws.column_dimensions[col_letter].width = max(len(h_name) + 5, 14)

            header_specs.append((
                h_name,
                {
                    'font': styles['font_header'],
                    'fill': header_fill,
                    'alignment': styles['align_center'],
                    'border': styles['border_thin'],
                },
            ))

        col_names = [c['name'] for c in cls.IMPORT_TEMPLATE_COLUMNS]

        if 'condition' in col_names:
            c_idx = col_names.index('condition') + 1
            c_letter = get_column_letter(c_idx)
            dv_cond = DataValidation(type="list", formula1='"new,used,refurbished"', allow_blank=True)
            dv_cond.error = 'Selecciona un valor válido: new, used, refurbished'
            dv_cond.errorTitle = 'Condición no válida'
            if write_only:
                ws.data_validations.append(dv_cond)
            else:
                ws.add_data_validation(dv_cond)
            dv_cond.add(f"{c_letter}2:{c_letter}{validation_max_row}")

        if 'tax_rate' in col_names:
            t_idx = col_names.index('tax_rate') + 1
            t_letter = get_column_letter(t_idx)
            dv_tax = DataValidation(type="list", formula1='"21.00,10.50,0.00"', allow_blank=True)
            dv_tax.error = 'Selecciona una alícuota válida: 21.00, 10.50 o 0.00'
            dv_tax.errorTitle = 'Alícuota IVA no válida'
            if write_only:
                ws.data_validations.append(dv_tax)
            else:
                ws.add_data_validation(dv_tax)
            dv_tax.add(f"{t_letter}2:{t_letter}{validation_max_row}")

        cls._append_styled_row(ws, 1, header_specs, write_only=write_only, height=28)

    @classmethod
    def _populate_guide_sheets(cls, wb, styles: Dict[str, object], write_only: bool = False) -> None:
        """Genera las hojas 'Guía y Ejemplos' y 'Guía de Imágenes' compartidas con el importador."""
        ws2 = wb.create_sheet(title="Guía y Ejemplos")
        ws2.views.sheetView[0].showGridLines = True
        ws2.column_dimensions['A'].width = 18
        ws2.column_dimensions['B'].width = 18
        ws2.column_dimensions['C'].width = 24
        ws2.column_dimensions['D'].width = 80

        r = 1
        r = cls._append_styled_row(
            ws2, r, [("GUÍA DE CAMPOS PARA IMPORTACIÓN MASIVA DE PRODUCTOS", {'font': styles['font_title']})], write_only
        )
        r = cls._append_styled_row(
            ws2, r, [("Bulonera Alvear - Plantilla Oficial de Carga", {'font': styles['font_subtitle']})], write_only
        )
        r = cls._append_styled_row(ws2, r, [], write_only)
        r = cls._append_styled_row(
            ws2, r, [("Explicación de Colores en la Hoja 'Productos':", {'font': styles['font_bold']})], write_only
        )

        legend_items = [
            ("Verde", "Campos obligatorios requeridos para todo producto (code y price).", styles['fill_green']),
            ("Azul Marino", "Datos del catálogo comercial e impositivos (categoría, stock, IVA Res. 4/2025, tags, imágenes).", styles['fill_navy']),
            ("Acero / Gris", "Dimensiones y especificaciones técnicas para bulonería y ferretería (diámetro, largo, norma, grado).", styles['fill_slate']),
            ("Azul Claro", "Identificadores universales EAN/MPN, categorización de Google, SEO y FAQs.", styles['fill_blue']),
        ]
        for color_name, desc, fill in legend_items:
            r = cls._append_styled_row(
                ws2,
                r,
                [
                    (color_name, {'fill': fill, 'font': styles['font_header'], 'alignment': styles['align_center'], 'border': styles['border_thin']}),
                    (desc, {'font': styles['font_regular'], 'alignment': styles['align_left']}),
                ],
                write_only,
            )

        r = cls._append_styled_row(ws2, r, [], write_only)
        r = cls._append_styled_row(ws2, r, [("Regla de Nombres Automáticos:", {'font': styles['font_bold']})], write_only)
        r = cls._append_styled_row(
            ws2,
            r,
            [("Si un producto incluye 'diameter' y 'length', y su 'name' no contiene las medidas, el sistema genera automáticamente: {nombre} {diámetro} x {longitud}.", {'font': styles['font_regular']})],
            write_only,
        )
        r = cls._append_styled_row(ws2, r, [], write_only)

        guide_headers = ["Columna", "Obligatorio", "Tipo de Dato", "Regla de Negocio / Valor por Defecto"]
        r = cls._append_styled_row(
            ws2,
            r,
            [
                (gh, {'font': styles['font_header'], 'fill': styles['fill_navy'], 'alignment': styles['align_center'], 'border': styles['border_thin']})
                for gh in guide_headers
            ],
            write_only,
            height=24,
        )

        for col_spec in cls.IMPORT_TEMPLATE_COLUMNS:
            req_text = "SÍ (Obligatorio)" if col_spec['required'] else "Opcional"
            req_style = {
                'font': styles['font_bold'] if col_spec['required'] else styles['font_regular'],
                'alignment': styles['align_center'],
                'border': styles['border_thin'],
            }
            if col_spec['required']:
                req_style['fill'] = styles['fill_light_gray']

            r = cls._append_styled_row(
                ws2,
                r,
                [
                    (col_spec['name'], {'font': styles['font_bold'], 'alignment': styles['align_left'], 'border': styles['border_thin']}),
                    (req_text, req_style),
                    (col_spec['type_desc'], {'font': styles['font_regular'], 'alignment': styles['align_left'], 'border': styles['border_thin']}),
                    (col_spec['rule'], {'font': styles['font_regular'], 'alignment': styles['align_left'], 'border': styles['border_thin']}),
                ],
                write_only,
            )

        r = cls._append_styled_row(ws2, r, [], write_only)
        r = cls._append_styled_row(
            ws2, r, [("EJEMPLOS PRÁCTICOS DE CARGA (3 CASOS REALES)", {'font': styles['font_title']})], write_only
        )
        r = cls._append_styled_row(
            ws2, r, [("Puedes consultar y copiar estos ejemplos para familiarizarte con los formatos:", {'font': styles['font_subtitle']})], write_only
        )
        r = cls._append_styled_row(ws2, r, [], write_only)

        r = cls._append_styled_row(
            ws2,
            r,
            [
                (col_spec['name'], {'font': styles['font_header'], 'fill': styles['fill_slate'], 'alignment': styles['align_center'], 'border': styles['border_thin']})
                for col_spec in cls.IMPORT_TEMPLATE_COLUMNS
            ],
            write_only,
            height=22,
        )

        for s_key in ('sample_1', 'sample_2', 'sample_3'):
            r = cls._append_styled_row(
                ws2,
                r,
                [
                    (col_spec.get(s_key, ''), {'font': styles['font_regular'], 'alignment': styles['align_left'], 'border': styles['border_thin']})
                    for col_spec in cls.IMPORT_TEMPLATE_COLUMNS
                ],
                write_only,
            )

        ws3 = wb.create_sheet(title="Guía de Imágenes")
        ws3.views.sheetView[0].showGridLines = True
        ws3.column_dimensions['A'].width = 30
        ws3.column_dimensions['B'].width = 85

        r3 = 1
        r3 = cls._append_styled_row(ws3, r3, [("GUÍA DE CARGA Y GESTIÓN DE IMÁGENES", {'font': styles['font_title']})], write_only)
        r3 = cls._append_styled_row(ws3, r3, [("Bulonera Alvear - Pipeline WebP y CDN", {'font': styles['font_subtitle']})], write_only)
        r3 = cls._append_styled_row(ws3, r3, [], write_only)

        img_rules = [
            ("1. Directorio en el Servidor", "Las fotos deben subirse previamente a la carpeta:\nmedia/photos/products/original/\n(a través del panel de Media Bank o SSH/SFTP)."),
            ("2. Formatos Soportados", "Se admiten formatos .jpg, .jpeg, .png y .webp. El servidor optimiza y genera automáticamente las variantes responsivas en WebP."),
            ("3. Nombres de Archivo", "Usar nombres en minúsculas, sin espacios ni caracteres especiales (ej. 'tornillo-hexagonal-m8.jpg')."),
            ("4. Imagen Principal ('images')", "Se especifica el nombre exacto de un único archivo (ej. 'bulon-g2-14112.jpg'). Si el producto ya existe y este campo se deja vacío, conserva la imagen actual."),
            ("5. Galería Secundaria ('gallery')", "Múltiples imágenes separadas por comas SIN espacios (ej. 'foto1.jpg,foto2.jpg,foto3.jpg'). En actualizaciones, si se especifican fotos en este campo, reemplaza la galería anterior."),
            ("6. Preguntas Frecuentes ('faq')", "Se cargan asociadas a la subcategoría en formato:\n\"¿Pregunta 1?\" Respuesta 1, \"¿Pregunta 2?\" Respuesta 2"),
        ]
        for title, desc in img_rules:
            r3 = cls._append_styled_row(
                ws3,
                r3,
                [
                    (title, {'font': styles['font_bold'], 'alignment': Alignment(horizontal="left", vertical="top"), 'border': styles['border_thin']}),
                    (desc, {'font': styles['font_regular'], 'alignment': styles['align_wrap'], 'border': styles['border_thin']}),
                ],
                write_only,
            )

    @classmethod
    def generate_import_template_workbook(cls, mode: str = 'full') -> io.BytesIO:
        """
        Genera en memoria un archivo Excel (.xlsx) estructurado y formateado
        para la carga masiva de productos o actualización rápida de precios.

        # POR QUÉ:
        # Los operadores de Django Admin necesitan una plantilla con las 33 columnas
        # exactas soportadas por el importador, con formato texto '@' en códigos y
        # dimensiones para evitar que Excel transforme '1/4' en fechas o trunque ceros
        # iniciales, y con hojas de guía pedagógicas integradas.
        #
        # REGLA:
        # En mode='full' la Hoja 1 ('Productos') se entrega limpia (solo encabezados)
        # para que el operador no ingiera accidentalmente filas de ejemplo a producción.
        # Los ejemplos y guías residen en la Hoja 2 ('Guía y Ejemplos') y Hoja 3 ('Guía de Imágenes').
        """
        wb = openpyxl.Workbook()
        styles = cls._get_excel_styles()

        if mode == 'prices':
            ws1 = wb.active
            ws1.title = "Lista_Precios"
            ws1.views.sheetView[0].showGridLines = True
            ws1.freeze_panes = "A2"
            ws1.row_dimensions[1].height = 28

            headers = ['code', 'price']
            for col_idx, h in enumerate(headers, 1):
                cell = ws1.cell(row=1, column=col_idx, value=h)
                cell.font = styles['font_header']
                cell.fill = styles['fill_green']
                cell.alignment = styles['align_center']
                cell.border = styles['border_thin']
                col_letter = get_column_letter(col_idx)
                ws1.column_dimensions[col_letter].width = 20
                if h == 'code':
                    ws1.column_dimensions[col_letter].number_format = '@'

            ws2 = wb.create_sheet(title="Instrucciones")
            ws2.views.sheetView[0].showGridLines = True
            ws2.append(["INSTRUCCIONES PARA ACTUALIZACIÓN RÁPIDA DE PRECIOS"])
            ws2.cell(row=1, column=1).font = styles['font_title']
            ws2.append(["Bulonera Alvear - Gestión Administrativa"])
            ws2.cell(row=2, column=1).font = styles['font_subtitle']
            ws2.append([])

            instrucciones = [
                ("1. Columna 'code'", "Debe coincidir exactamente con el código del producto en el catálogo. Se preservan ceros a la izquierda."),
                ("2. Columna 'price'", "Nuevo precio final con IVA incluido. Admite formatos '1234.56', '1.234,56' o '$ 1234,56'."),
                ("3. Códigos inexistentes", "Los códigos que no existan en la base de datos se informarán como error en el resumen y no afectarán al resto."),
                ("4. Campos inalterados", "Esta planilla solo actualiza el precio y la fecha de modificación; no altera descripciones, categorías ni SEO."),
            ]
            for title, desc in instrucciones:
                r = ws2.max_row + 1
                c1 = ws2.cell(row=r, column=1, value=title)
                c1.font = styles['font_bold']
                c2 = ws2.cell(row=r, column=2, value=desc)
                c2.font = styles['font_regular']

            ws2.column_dimensions['A'].width = 25
            ws2.column_dimensions['B'].width = 85

        else:
            ws1 = wb.active
            ws1.title = "Productos"
            cls._configure_products_sheet(ws1, styles, write_only=False, validation_max_row=2000)
            cls._populate_guide_sheets(wb, styles, write_only=False)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @classmethod
    def export_products_workbook(
        cls,
        queryset: Optional[QuerySet] = None,
        category_id: Optional[int] = None,
        subcategory_id: Optional[int] = None,
        only_available: bool = False,
    ) -> tempfile.SpooledTemporaryFile:
        """
        Exporta el catálogo completo o filtrado de productos a un archivo Excel (.xlsx)
        compatible 100% round-trip con el importador oficial.

        # QUÉ:
        # Genera un libro Excel de 3 hojas ('Productos', 'Guía y Ejemplos', 'Guía de Imágenes')
        # con las 33 columnas canónicas definidas en IMPORT_TEMPLATE_COLUMNS.
        #
        # POR QUÉ:
        # Un Workbook estándar o pandas.to_excel() en catálogos de +14.000 productos consume
        # 180-320 MB de RAM y provoca reciclaje de workers uWSGI (reload-on-rss=256) o timeouts
        # de 60s en OpenLiteSpeed (HTTP 500). Usar write_only=True, pre-carga relacional O(1),
        # values().iterator(chunk_size=1000) y SpooledTemporaryFile mantiene la RAM plana (<20 MB).
        #
        # REGLA:
        # Las columnas de formato texto '@' (code, diameter, length, gtin, mpn) se emiten como
        # strings explícitos y todo texto que inicie con '=', '+', '-', '@' fuerza data_type='s'
        # para prevenir Formula Injection y corrupción al abrir en Excel.
        """
        queryset_was_provided = queryset is not None
        if queryset is None:
            queryset = Product.objects.all()

        if only_available:
            queryset = queryset.filter(is_available=True)

        if category_id is not None:
            queryset = queryset.filter(category_id=category_id)

        if subcategory_id is not None:
            # Subconsulta sobre la tabla intermedia para filtrar sin duplicados ni DISTINCT costoso.
            subcat_product_ids = Product.subcategories.through.objects.filter(
                subcategory_id=subcategory_id
            ).values('product_id')
            queryset = queryset.filter(pk__in=subcat_product_ids)

        queryset = queryset.order_by('id')

        # 1. Pre-carga relacional en O(1) consultas planas para eliminar N+1 queries.
        is_filtered = bool(queryset_was_provided or only_available or category_id is not None or subcategory_id is not None)

        subcat_qs = Product.subcategories.through.objects.all()
        rel_subcat_qs = Product.related_subcategories.through.objects.all()
        tag_qs = Product.tags.through.objects.all()
        gallery_qs = ProductGallery.objects.all().order_by('id')

        if is_filtered:
            product_id_subquery = queryset.values('pk')
            subcat_qs = subcat_qs.filter(product_id__in=product_id_subquery)
            rel_subcat_qs = rel_subcat_qs.filter(product_id__in=product_id_subquery)
            tag_qs = tag_qs.filter(product_id__in=product_id_subquery)
            gallery_qs = gallery_qs.filter(product_id__in=product_id_subquery)

        subcats_by_product: Dict[int, List[str]] = defaultdict(list)
        subcat_ids_by_product: Dict[int, List[int]] = defaultdict(list)
        for pid, sc_id, sc_name in subcat_qs.values_list(
            'product_id', 'subcategory_id', 'subcategory__subcategory_name'
        ):
            if sc_name:
                subcats_by_product[pid].append(sc_name)
            if sc_id:
                subcat_ids_by_product[pid].append(sc_id)

        rel_subcats_by_product: Dict[int, List[str]] = defaultdict(list)
        for pid, sc_name in rel_subcat_qs.values_list('product_id', 'subcategory__subcategory_name'):
            if sc_name:
                rel_subcats_by_product[pid].append(sc_name)

        tags_by_product: Dict[int, List[str]] = defaultdict(list)
        for pid, tag_name in tag_qs.values_list('product_id', 'producttag__name'):
            if tag_name:
                tags_by_product[pid].append(tag_name)

        gallery_by_product: Dict[int, List[str]] = defaultdict(list)
        for pid, legacy_img, asset_file in gallery_qs.values_list('product_id', 'image', 'image_asset__file'):
            img_path = asset_file or legacy_img
            if img_path:
                gallery_by_product[pid].append(os.path.basename(img_path))

        faqs_by_subcat: Dict[int, List[str]] = defaultdict(list)
        for sc_id, question, answer in (
            FAQ.objects.filter(is_active=True, subcategory_id__isnull=False)
            .order_by('order', 'id')
            .values_list('subcategory_id', 'question', 'answer')
        ):
            q_clean = (question or '').strip()
            a_clean = (answer or '').strip()
            if q_clean and a_clean:
                faqs_by_subcat[sc_id].append(f'"{q_clean}" {a_clean}')

        # 2. Configurar libro write-only y hoja principal antes del primer append().
        wb = openpyxl.Workbook(write_only=True)
        styles = cls._get_excel_styles()

        ws1 = wb.create_sheet(title="Productos")
        cls._configure_products_sheet(ws1, styles, write_only=True, validation_max_row=50000)

        text_format_cols = {
            c['name'] for c in cls.IMPORT_TEMPLATE_COLUMNS if c.get('format') == '@'
        }
        col_order = [c['name'] for c in cls.IMPORT_TEMPLATE_COLUMNS]

        # 3. Streaming de filas escalares desde base de datos en chunks de 1.000.
        product_values = queryset.values(
            'id', 'code', 'price', 'name', 'diameter', 'length',
            'description', 'stock', 'category__category_name',
            'diameter_relation', 'thread_formats_relation',
            'tax_rate', 'brand', 'condition', 'images', 'image__file',
            'norm', 'grade', 'material', 'colour', 'type', 'form',
            'thread_formats', 'origin', 'gtin', 'mpn', 'google_category',
            'meta_title', 'meta_description', 'meta_keywords',
        ).iterator(chunk_size=1000)

        for prod in product_values:
            pid = prod['id']
            main_img_path = prod.get('images') or prod.get('image__file') or ''
            main_img_name = os.path.basename(main_img_path) if main_img_path else ''

            raw_tax = prod.get('tax_rate')
            tax_rate_str = f"{Decimal(str(raw_tax)):.2f}" if raw_tax is not None else '21.00'

            faq_entries: List[str] = []
            seen_faqs = set()
            for sc_id in subcat_ids_by_product.get(pid, []):
                for faq_item in faqs_by_subcat.get(sc_id, []):
                    if faq_item not in seen_faqs:
                        seen_faqs.add(faq_item)
                        faq_entries.append(faq_item)

            row_map = {
                'code': prod.get('code') or '',
                'price': prod.get('price') if prod.get('price') is not None else '',
                'name': prod.get('name') or '',
                'diameter': prod.get('diameter') or '',
                'length': prod.get('length') or '',
                'description': prod.get('description') or '',
                'stock': prod.get('stock') if prod.get('stock') is not None else 0,
                'category': prod.get('category__category_name') or '',
                'subcategories': ', '.join(subcats_by_product.get(pid, [])),
                'related_subcategories': ', '.join(rel_subcats_by_product.get(pid, [])),
                'diameter_relation': prod.get('diameter_relation') or '',
                'thread_formats_relation': prod.get('thread_formats_relation') or '',
                'tags': ', '.join(tags_by_product.get(pid, [])),
                'tax_rate': tax_rate_str,
                'brand': prod.get('brand') or '',
                'condition': prod.get('condition') or 'new',
                'images': main_img_name,
                'gallery': ','.join(gallery_by_product.get(pid, [])),
                'norm': prod.get('norm') or '',
                'grade': prod.get('grade') or '',
                'material': prod.get('material') or '',
                'colour': prod.get('colour') or '',
                'type': prod.get('type') or '',
                'form': prod.get('form') or '',
                'thread_formats': prod.get('thread_formats') or '',
                'origin': prod.get('origin') or '',
                'gtin': prod.get('gtin') or '',
                'mpn': prod.get('mpn') or '',
                'google_category': prod.get('google_category') or '',
                'faq': ', '.join(faq_entries),
                'meta_title': prod.get('meta_title') or '',
                'meta_description': prod.get('meta_description') or '',
                'meta_keywords': prod.get('meta_keywords') or '',
            }

            row_cells = [
                cls._sanitize_export_scalar(
                    ws1,
                    row_map[col_name],
                    force_text=(col_name in text_format_cols),
                )
                for col_name in col_order
            ]
            ws1.append(row_cells)

        # 4. Agregar hojas auxiliares de documentación idénticas a la plantilla oficial.
        cls._populate_guide_sheets(wb, styles, write_only=True)

        # 5. Volcar a archivo temporal con rollover automático a disco >10 MB (evita OOM).
        tmp_file = tempfile.SpooledTemporaryFile(
            max_size=10 * 1024 * 1024,
            prefix='bulonera_export_',
            suffix='.xlsx',
        )
        wb.save(tmp_file)
        tmp_file.seek(0)
        return tmp_file
    
    @staticmethod
    def import_from_file(
        file_or_path,
        dry_run: bool = False,
        update_prices: bool = False,
        preserve_existing_stock: bool = False,
    ) -> ImportResult:
        """
        Importa/actualiza productos desde Excel o CSV.
        Migrado desde ProductAdmin.process_import().
        Clave de upsert: `code`
        
        Args:
            file_or_path: Archivo o ruta al archivo Excel/CSV
            dry_run: Si es True, simula la importación sin guardar
            update_prices: Si es True, solo actualiza precios
            preserve_existing_stock: Si es True, ignora la columna stock en productos existentes
        
        Returns:
            ImportResult con estadísticas de la importación
        """
        try:
            # POR QUÉ: Evita que llamadas programáticas con update_prices=True ejecuten _process_row completo.
            if update_prices and not dry_run:
                return ProductService.update_prices_from_file(file_or_path)

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
                                item, dry_run, update_prices, result, processed_subcategories,
                                preserve_existing_stock=preserve_existing_stock,
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
                        # REGLA: Incluir discount_percentage en update_fields para persistir el recálculo
                        # de ofertas que Product.save() realiza automáticamente en memoria.
                        product.save(update_fields=['price', 'discount_percentage', 'modified_date'])
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

    # ============================================================
    # MÉTODOS DE IMPORTACIÓN Y ACTUALIZACIÓN POR LOTES (CHUNKED)
    # ============================================================

    @classmethod
    def start_bulk_upload_session(
        cls,
        file_or_path,
        mode: str,
        user_id: int,
        preserve_existing_stock: bool = False,
    ) -> dict:
        """
        Inicia una sesión de carga masiva fraccionada en lotes HTTP.

        # QUÉ: Analiza el archivo (.xlsx/.csv), valida que contenga filas, divide los datos
        # en lotes comprimidos en caché y genera un identificador de sesión 'upload_id'.
        #
        # POR QUÉ:
        # Previene el error HTTP 500 provocado por el timeout de 60s en OpenLiteSpeed y 120s
        # en uWSGI cuando se procesan planillas de 10.000 a 14.000 filas en una sola petición.
        #
        # REGLA:
        # El tamaño de lote es 250 para importación completa (por complejidad de FK/M2M/imágenes)
        # y 500 para precios (operación ultra-liviana con bulk_update).
        """
        if mode not in ('import', 'prices'):
            raise ValueError(f"Modo no soportado: '{mode}'. Debe ser 'import' o 'prices'.")

        try:
            data = cls._parse_file(file_or_path)
        except Exception as e:
            logger.error(f"Error al parsear archivo en start_bulk_upload_session: {e}")
            return {'success': False, 'error': f"Formato o estructura de archivo no válida: {str(e)}"}

        if not data:
            return {'success': False, 'error': "El archivo subido no contiene filas con datos o está vacío."}

        upload_id = uuid.uuid4().hex
        chunk_size = cls.PRICES_CHUNK_SIZE if mode == 'prices' else cls.IMPORT_CHUNK_SIZE
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        total_chunks = len(chunks)

        # Guardar cada lote comprimido con zlib para optimizar memoria en Redis
        for i, chunk in enumerate(chunks):
            chunk_key = f"store:bulk:{upload_id}:chunk:{i}"
            compressed_bytes = zlib.compress(json.dumps(chunk).encode('utf-8'))
            cache.set(chunk_key, compressed_bytes, timeout=cls.BULK_UPLOAD_CACHE_TIMEOUT)

        meta = {
            'upload_id': upload_id,
            'mode': mode,
            'user_id': user_id,
            'preserve_existing_stock': bool(preserve_existing_stock),
            'total_rows': len(data),
            'total_chunks': total_chunks,
            'chunk_size': chunk_size,
            'processed_rows': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'image_warnings': 0,
            'completed_chunks': [],
            'error_details': [],
            'tags_created': [],
            'created_at': timezone.now().isoformat(),
            'is_done': False,
        }
        meta_key = f"store:bulk:{upload_id}:meta"
        cache.set(meta_key, meta, timeout=cls.BULK_UPLOAD_CACHE_TIMEOUT)

        logger.info(
            f"Iniciada sesión de carga masiva {upload_id} (modo={mode}, filas={len(data)}, "
            f"lotes={total_chunks}, usuario={user_id}, preserve_existing_stock={bool(preserve_existing_stock)})"
        )

        return {
            'success': True,
            'upload_id': upload_id,
            'mode': mode,
            'total_rows': len(data),
            'total_chunks': total_chunks,
            'chunk_size': chunk_size,
        }

    @classmethod
    def process_bulk_upload_chunk(cls, upload_id: str, chunk_index: int, user_id: int) -> dict:
        """
        Procesa un lote individual de la sesión de carga masiva.

        # QUÉ: Recupera el lote de la memoria caché, ejecuta la persistencia en base de datos,
        # actualiza los acumuladores en caché y libera el espacio del lote procesado.
        #
        # REGLA:
        # Idempotencia: Si un lote ya fue procesado y se reintenta por microcorte de red,
        # retorna el estado acumulado sin duplicar métricas ni reejecutar escrituras.
        # Seguridad: Valida que el user_id solicitante coincida con el iniciador de la sesión.
        """
        meta_key = f"store:bulk:{upload_id}:meta"
        meta = cache.get(meta_key)
        if not meta:
            return {
                'success': False,
                'error': "La sesión de carga ha expirado o no existe. Por favor vuelva a subir el archivo."
            }

        # Control anti-IDOR
        if meta.get('user_id') != user_id:
            return {
                'success': False,
                'error': "No tiene permisos para procesar esta sesión de carga.",
                'permission_denied': True
            }

        # Idempotencia defensiva ante reintentos de red del navegador
        completed_chunks = meta.get('completed_chunks', [])
        if chunk_index in completed_chunks:
            percent = int((meta['processed_rows'] / meta['total_rows']) * 100) if meta['total_rows'] > 0 else 100
            return {
                'success': True,
                'upload_id': upload_id,
                'chunk_index': chunk_index,
                'total_chunks': meta['total_chunks'],
                'processed_rows': meta['processed_rows'],
                'total_rows': meta['total_rows'],
                'percent': min(percent, 100),
                'created': meta['created'],
                'updated': meta['updated'],
                'errors': meta['errors'],
                'image_warnings': meta['image_warnings'],
                'error_details': meta['error_details'][:10],
                'total_errors': meta['errors'],
                'tags_created': meta.get('tags_created', []),
                'is_done': meta['is_done'],
            }

        if chunk_index < 0 or chunk_index >= meta['total_chunks']:
            return {'success': False, 'error': f"Índice de lote inválido: {chunk_index}."}

        chunk_key = f"store:bulk:{upload_id}:chunk:{chunk_index}"
        compressed_bytes = cache.get(chunk_key)
        if not compressed_bytes:
            return {
                'success': False,
                'error': f"El lote {chunk_index} no fue encontrado en la memoria temporal (posible expiración)."
            }

        try:
            rows = json.loads(zlib.decompress(compressed_bytes).decode('utf-8'))
        except Exception as e:
            logger.error(f"Error descomprimiendo lote {chunk_index} para sesión {upload_id}: {e}")
            return {'success': False, 'error': f"Error al leer datos del lote {chunk_index}."}

        chunk_offset = chunk_index * meta['chunk_size']

        if meta['mode'] == 'prices':
            chunk_result = cls._process_price_chunk(rows, chunk_offset)
        else:
            chunk_result = cls._process_import_chunk(
                rows,
                chunk_offset,
                preserve_existing_stock=bool(meta.get('preserve_existing_stock', False)),
            )

        # Actualizar acumuladores en meta
        meta['processed_rows'] += len(rows)
        meta['created'] += chunk_result.get('created', 0)
        meta['updated'] += chunk_result.get('updated', 0)
        meta['errors'] += chunk_result.get('errors', 0)
        meta['image_warnings'] += chunk_result.get('image_warnings', 0)

        if chunk_result.get('tags_created'):
            meta['tags_created'].extend(chunk_result['tags_created'])

        if chunk_result.get('error_details'):
            # Almacenar hasta 50 ejemplos para feedback detallado al operador
            max_samples = 50
            space_left = max(0, max_samples - len(meta['error_details']))
            if space_left > 0:
                meta['error_details'].extend(chunk_result['error_details'][:space_left])

        meta['completed_chunks'].append(chunk_index)
        is_done = (len(meta['completed_chunks']) >= meta['total_chunks']) or (meta['processed_rows'] >= meta['total_rows'])
        meta['is_done'] = is_done

        # Liberar memoria del lote procesado inmediatamente
        cache.delete(chunk_key)
        cache.set(meta_key, meta, timeout=cls.BULK_UPLOAD_CACHE_TIMEOUT)

        percent = int((meta['processed_rows'] / meta['total_rows']) * 100) if meta['total_rows'] > 0 else 100

        return {
            'success': True,
            'upload_id': upload_id,
            'chunk_index': chunk_index,
            'total_chunks': meta['total_chunks'],
            'processed_rows': meta['processed_rows'],
            'total_rows': meta['total_rows'],
            'percent': min(percent, 100),
            'created': meta['created'],
            'updated': meta['updated'],
            'errors': meta['errors'],
            'image_warnings': meta['image_warnings'],
            'error_details': meta['error_details'][:10],
            'total_errors': meta['errors'],
            'tags_created': meta['tags_created'],
            'is_done': is_done,
        }

    @classmethod
    def _process_price_chunk(cls, rows: list, chunk_offset: int) -> dict:
        """
        Procesa un lote de precios masivos usando bulk_update en una sola consulta.

        # PERF:
        # Agrupa la consulta de existencia con un solo SELECT code__in=[...] y la persistencia
        # con un solo bulk_update([...], batch_size=500), reduciendo el tiempo de 500 filas
        # de ~15 segundos a menos de 250 milisegundos.
        """
        result = {
            'created': 0,
            'updated': 0,
            'errors': 0,
            'image_warnings': 0,
            'error_details': []
        }

        valid_items = []
        for idx, item in enumerate(rows):
            row_num = chunk_offset + idx + 2
            if not item.get('code') or pd.isna(item.get('code')):
                result['errors'] += 1
                result['error_details'].append((row_num, "Falta el código del producto"))
                continue
            if not item.get('price') or pd.isna(item.get('price')):
                result['errors'] += 1
                result['error_details'].append((row_num, f"Producto {item.get('code')}: Falta el precio"))
                continue

            code = str(item['code']).strip()
            if code.endswith('.0'):
                code = code[:-2]

            try:
                clean_price = cls._sanitize_price(item['price'])
                valid_items.append((row_num, code, clean_price))
            except ValueError as e:
                result['errors'] += 1
                result['error_details'].append((row_num, f"Código {code}: {str(e)}"))

        if not valid_items:
            return result

        codes = [item[1] for item in valid_items]
        products_by_code = {p.code: p for p in Product.objects.filter(code__in=codes)}

        # Fallback defensivo para códigos legacy que tengan .0 en base de datos
        missing_codes = [c for c in codes if c not in products_by_code and '.' not in c]
        if missing_codes:
            legacy_map = {f"{c}.0": c for c in missing_codes}
            for p in Product.objects.filter(code__in=list(legacy_map.keys())):
                clean_c = legacy_map[p.code]
                products_by_code[clean_c] = p

        products_to_update = []
        now = timezone.now()
        for row_num, code, clean_price in valid_items:
            product = products_by_code.get(code)
            if not product:
                result['errors'] += 1
                result['error_details'].append((row_num, f"Código {code} no existe en la base de datos"))
                continue

            product.price = clean_price
            product.modified_date = now
            if product.is_on_sale and product.sale_price is not None and product.price > 0:
                product.discount_percentage = int(((product.price - product.sale_price) / product.price) * 100)
            elif product.is_on_sale and (product.price <= 0 or product.sale_price is None):
                product.discount_percentage = None

            products_to_update.append(product)
            result['updated'] += 1

        if products_to_update:
            with transaction.atomic():
                Product.objects.bulk_update(
                    products_to_update,
                    ['price', 'discount_percentage', 'modified_date'],
                    batch_size=500
                )

        return result

    @classmethod
    def _process_import_chunk(
        cls,
        rows: list,
        chunk_offset: int,
        preserve_existing_stock: bool = False,
    ) -> dict:
        """
        Procesa un lote de importación completa de productos con aislamiento transaccional por fila.
        """
        result = ImportResult()
        processed_subcategories = set()

        for idx, item in enumerate(rows):
            row_num = chunk_offset + idx + 2
            try:
                with transaction.atomic():
                    created = cls._process_row(
                        item, dry_run=False, update_prices=False,
                        result=result, processed_subcategories=processed_subcategories,
                        preserve_existing_stock=preserve_existing_stock,
                    )
                    if created:
                        result.created += 1
                    else:
                        result.updated += 1
            except Exception as e:
                result.errors += 1
                result.error_details.append((row_num, str(e)))
                logger.error(f"Error importando fila {row_num} (código={item.get('code', '?')}): {e}")

        return {
            'created': result.created,
            'updated': result.updated,
            'errors': result.errors,
            'image_warnings': result.image_warnings,
            'error_details': result.error_details,
            'tags_created': result.tags_created,
        }

    @classmethod
    def cancel_bulk_upload_session(cls, upload_id: str, user_id: int) -> bool:
        """
        Cancela una sesión de carga masiva y purga sus recursos en caché.
        """
        meta_key = f"store:bulk:{upload_id}:meta"
        meta = cache.get(meta_key)
        if not meta:
            return False
        if meta.get('user_id') != user_id:
            return False

        total_chunks = meta.get('total_chunks', 0)
        for i in range(total_chunks):
            cache.delete(f"store:bulk:{upload_id}:chunk:{i}")
        cache.delete(meta_key)
        logger.info(f"Sesión de carga masiva {upload_id} cancelada y purgada por el usuario {user_id}")
        return True
    
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
    def _sanitize_stock(stock_value) -> int:
        """
        Valida y convierte un valor de stock a entero no negativo.

        # REGLA: Acepta enteros ('0', '50') y decimales exactos en cero exportados por Excel
        # ('50.0', '50.00', '50,0', '50,00'). Rechaza explícitamente separadores de miles ('1.000'),
        # fracciones ('10,5'), negativos o texto para impedir conversiones silenciosas a 0 o 1.
        """
        if isinstance(stock_value, bool):
            raise ValueError(f"Valor booleano no permitido para stock: '{stock_value}'")
        if stock_value is None or (isinstance(stock_value, float) and pd.isna(stock_value)):
            raise ValueError("Stock vacío o nulo")

        if isinstance(stock_value, int):
            if stock_value < 0:
                raise ValueError(f"Stock negativo no permitido: {stock_value}")
            return stock_value

        if isinstance(stock_value, float):
            if stock_value < 0 or not stock_value.is_integer():
                raise ValueError(f"El stock debe ser un entero no negativo: '{stock_value}'")
            return int(stock_value)

        raw_str = str(stock_value).strip()
        # CUIDADO: Usar {1,2} y NO 0+ para rechazar '1.000' (3 dígitos tras punto = miles ambiguo).
        if not re.fullmatch(r'\d+(?:[.,]0{1,2})?', raw_str):
            raise ValueError(
                f"Formato de stock inválido o ambiguo: '{stock_value}' "
                f"(use un número entero sin separador de miles)"
            )

        int_part = re.split(r'[.,]', raw_str, maxsplit=1)[0]
        return int(int_part)
    
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
        
        # REGLA DEFENSIVA: Descartar filas 100% vacías generadas por formateo de celdas en Excel
        df = df.dropna(how='all')
        if df.empty:
            return []
        
        # PASO 2: Normalizar headers
        df.columns = df.columns.astype(str).str.lower().str.strip()
        
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
    def _process_row(
        item: dict,
        dry_run: bool,
        update_prices: bool,
        result: ImportResult,
        processed_subcategories: set,
        preserve_existing_stock: bool = False,
    ) -> bool:
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
        
        # PERF: Evitar encolar tareas redundantes a Celery en cargas masivas,
        # ya que las imágenes se procesan sincrónicamente en _process_main_image.
        product._skip_image_task = True
        
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
        # REGLA: Celdas vacías o columna ausente conservan el stock actual en productos existentes
        # (solo inicializan en 0 en altas nuevas). Si preserve_existing_stock=True, se ignora la
        # columna stock en productos existentes para no pisar stock web con ceros antiguos/ERP.
        raw_stock = item.get('stock')
        has_stock_value = (
            raw_stock is not None
            and not (isinstance(raw_stock, float) and pd.isna(raw_stock))
            and str(raw_stock).strip() != ''
        )
        if not has_stock_value:
            if created:
                product.stock = 0
        elif not created and preserve_existing_stock:
            pass
        else:
            try:
                product.stock = ProductService._sanitize_stock(raw_stock)
            except ValueError as e:
                raise ValueError(f"Stock inválido para código {code}: {str(e)}")
        
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

        # Campos de relación técnica (vacío conserva; '-' limpia explícitamente)
        for rel_field in ('diameter_relation', 'thread_formats_relation'):
            if rel_field in item and item[rel_field] is not None and not pd.isna(item[rel_field]):
                rel_val = str(item[rel_field]).strip()
                if rel_val == '-':
                    setattr(product, rel_field, '')
                elif rel_val != '':
                    setattr(product, rel_field, rel_val[:100])

        # Alícuota impositiva (Res. 4/2025)
        tax_col = None
        for col_name in ['tax_rate', 'iva', 'alicuota_iva', 'alicuota']:
            if col_name in item and item[col_name] is not None and not pd.isna(item[col_name]):
                tax_col = item[col_name]
                break
        if tax_col is not None:
            try:
                clean_rate_str = str(tax_col).replace('%', '').replace(',', '.').strip()
                product.tax_rate = Decimal(clean_rate_str)
            except Exception:
                pass
        
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

        # Procesar subcategorías relacionadas (soporta alias ProductRelation / productrelation tras lower())
        raw_related_subcats = None
        for rel_col in ('related_subcategories', 'productrelation', 'product_relation', 'ProductRelation'):
            if rel_col in item and item[rel_col] is not None and not pd.isna(item[rel_col]):
                candidate_str = str(item[rel_col]).strip()
                if candidate_str:
                    raw_related_subcats = candidate_str
                    break
        if raw_related_subcats == '-':
            product.related_subcategories.clear()
        elif raw_related_subcats:
            ProductService._process_related_subcategories(product, raw_related_subcats)
        
        # Procesar tags
        if 'tags' in item and item['tags'] and not pd.isna(item['tags']):
            ProductService._process_tags(
                product, str(item['tags']), result
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
    def _process_related_subcategories(product: Product, raw_str: str) -> None:
        """
        Vincula subcategorías relacionadas existentes sin crear subcategorías fantasma.

        REGLA: A diferencia de _process_subcategories, no ejecuta get_or_create para evitar
        crear subcategorías bajo una categoría padre equivocada o por errores de tipeo.
        """
        names = [s.strip() for s in raw_str.split(',') if s.strip()]
        found_subcats: List[SubCategory] = []
        seen_ids = set()

        for name in names:
            subcat = (
                SubCategory.objects.filter(subcategory_name__iexact=name).first()
                or SubCategory.objects.filter(slug=slugify(name)).first()
            )
            if not subcat:
                logger.warning(
                    "Subcategoría relacionada '%s' no encontrada para producto %s; se omite.",
                    name,
                    product.code,
                )
                continue
            if subcat.id not in seen_ids:
                seen_ids.add(subcat.id)
                found_subcats.append(subcat)

        if found_subcats:
            product.related_subcategories.set(found_subcats)

    @staticmethod
    def _process_tags(product: Product, tags_str: str, result: ImportResult) -> None:
        """Procesa los tags del producto desde un string separado por comas"""
        from store.models import ProductTag
        tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
        
        tags_to_assign = []
        for tag_name in tag_names:
            slug = slugify(tag_name)
            if not slug:
                continue
            
            tag, created = ProductTag.objects.get_or_create(
                slug=slug,
                defaults={'name': tag_name}
            )
            if created:
                result.tags_created.append(tag_name)
                
            tags_to_assign.append(tag)
            
        if tags_to_assign:
            product.tags.set(tags_to_assign)
    
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
    """Servicio para búsqueda de productos, telemetría agregada y exportación Excel de consultas."""

    DEFAULT_EXPORT_PERIOD_DAYS = 90
    ALLOWED_PERIOD_DAYS = {'7': 7, '30': 30, '90': 90, 'all': None}
    SEARCH_TELEMETRY_MAX_WRITES_PER_MIN = 30
    SEARCH_TELEMETRY_WRITES_WINDOW_SEC = 60
    SEARCH_TELEMETRY_MAX_NEW_TERMS_PER_10M = 15
    SEARCH_TELEMETRY_NEW_TERMS_WINDOW_SEC = 600
    SEARCH_TELEMETRY_GLOBAL_MAX_NEW_TERMS_PER_10M = 120

    # REGLA: Heurística de reducción de riesgo PII:
    # Detecta patrones comunes de datos personales (emails, teléfonos y documentos DNI/CUIT).
    # TRADE-OFF DOCUMENTADO: Códigos SKU comerciales puramente numéricos de 7 a 11 dígitos
    # (presentes en el catálogo, ej. 00100100001) que NO coincidan con ningún producto existente
    # serán descartados de SearchQuery para priorizar la no persistencia accidental de DNI o teléfonos.
    # El motor de búsqueda (search_products) sí evalúa dichos códigos normalmente contra el catálogo.
    _RE_EMAIL = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.IGNORECASE)
    _RE_DOC_STANDALONE = re.compile(r'\b\d{7,11}\b')
    _RE_CUIT_FORMATTED = re.compile(r'\b\d{2}[-.\s]\d{8}[-.\s]\d{1}\b')
    _RE_DNI_FORMATTED = re.compile(r'\b\d{1,2}\.\d{3}\.\d{3}\b')
    _RE_PHONE_LOCAL = re.compile(r'\b\d{3,4}[-.\s]\d{4}\b')
    _RE_PHONE_NATIONAL = re.compile(r'(?:\+?54\s?9?)?\s?(?:0?[1-9]\d{1,3})[-.\s]?(?:15[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b')
    _RE_BOT_UA = re.compile(
        r'(?:bot|crawl|spider|slurp|mediapartners|adsbot|bingpreview|facebookexternalhit|'
        r'whatsapp|telegrambot|discordbot|linkedinbot|embedly|pinterest|applebot|yandex|'
        r'baiduspider|duckduckbot|semrush|ahrefs|mj12bot|dotbot|petalbot|bytespider|'
        r'gptbot|claudebot|perplexitybot|headlesschrome|lighthouse|pagespeed|'
        r'python-requests|curl/|wget/|go-http-client)',
        re.IGNORECASE,
    )

    @classmethod
    def is_bot_user_agent(cls, user_agent: Optional[str]) -> bool:
        """
        Detecta User-Agents de crawlers, scrapers y previsualizadores de enlaces.

        POR QUÉ: /store/search/ es accesible para buscadores (SearchAction JSON-LD); filtrar
        bots en el servicio evita contaminar el ranking comercial sin bloquear robots.txt.
        """
        if not user_agent:
            return False
        return bool(cls._RE_BOT_UA.search(user_agent))

    @classmethod
    def contains_sensitive_pii(cls, text: str) -> bool:
        """
        Evalúa si el texto coincide con patrones comunes de datos personales (emails, teléfonos, DNI/CUIT).
        Permite búsquedas técnicas con medidas (ej. 12x1.5, 14x2 100, 3/8) al no sumar dígitos arbitrarios.
        """
        if not text:
            return False
        return bool(
            cls._RE_EMAIL.search(text) or
            cls._RE_DOC_STANDALONE.search(text) or
            cls._RE_CUIT_FORMATTED.search(text) or
            cls._RE_DNI_FORMATTED.search(text) or
            cls._RE_PHONE_LOCAL.search(text) or
            cls._RE_PHONE_NATIONAL.search(text)
        )

    @staticmethod
    def search_products(keyword: str) -> QuerySet:
        """
        Busca productos por palabra clave en múltiples campos y relaciones:
        código, nombre, descripción, marca, categoría y subcategorías.
        Aplica .distinct() para evitar duplicación cuando un producto coincide en varias subcategorías.
        """
        if not keyword:
            return Product.objects.filter(is_available=True)
        
        # SEC-109: Sanitizar y limitar longitud de palabra clave para prevenir DoS / ReDoS
        keyword = keyword.strip()[:100]
        if not keyword:
            return Product.objects.filter(is_available=True)
        
        return Product.objects.filter(
            Q(code__icontains=keyword) |
            Q(name__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(brand__icontains=keyword) |
            Q(category__category_name__icontains=keyword) |
            Q(subcategories__subcategory_name__icontains=keyword),
            is_available=True
        ).distinct().order_by('-created_date')
    
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

    @staticmethod
    def extract_telemetry_client_ip(request) -> str:
        """
        Extrae la IP del cliente para rate limiting de telemetría mitigando spoofing.

        POR QUÉ: OpenLiteSpeed es el único proxy reverso delante de Django y anexa la IP real
        al final de X-Forwarded-For; leer el último salto evita que un atacante falsifique
        el primer valor de la cabecera para evadir límites por IP.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if x_forwarded_for:
            hops = [part.strip() for part in x_forwarded_for.split(',') if part.strip()]
            if hops:
                return hops[-1]
        return (request.META.get('REMOTE_ADDR') or '').strip()

    @staticmethod
    def _hash_client_ip(client_ip: str) -> str:
        """Hashea la IP con SECRET_KEY para claves de caché sin almacenar IP en claro."""
        digest = hashlib.sha256(f"sq_rl:{settings.SECRET_KEY}:{client_ip}".encode("utf-8")).hexdigest()
        return digest[:16]

    @classmethod
    def _is_rate_limited(cls, cache_key: str, limit: int, timeout: int, scope: str) -> bool:
        """Evalúa umbral en Redis con degradación fail-closed para escrituras de telemetría."""
        try:
            cache.add(cache_key, 0, timeout=timeout)
            count = cache.incr(cache_key)
        except Exception:
            logger.warning("Rate limit telemetría omitido por fallo de caché (scope=%s)", scope)
            return True
        if count > limit:
            logger.warning("Rate limit de telemetría superado (scope=%s, count=%s, limit=%s)", scope, count, limit)
            return True
        return False

    @classmethod
    def is_write_rate_limited(cls, client_ip: Optional[str]) -> bool:
        """Verifica el límite Nivel 1 de escrituras por minuto para la IP dada."""
        if not client_ip:
            return False
        ip_hash = cls._hash_client_ip(client_ip)
        limit = getattr(settings, 'SEARCH_TELEMETRY_MAX_WRITES_PER_MIN', cls.SEARCH_TELEMETRY_MAX_WRITES_PER_MIN)
        return cls._is_rate_limited(
            f"store:sq_rl:writes:{ip_hash}",
            limit,
            cls.SEARCH_TELEMETRY_WRITES_WINDOW_SEC,
            "writes",
        )

    @classmethod
    def record_search_query(
        cls,
        keyword: str,
        results_count: int,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
        _skip_write_rate_limit: bool = False,
    ) -> bool:
        """
        Registra o actualiza métricas agregadas de una búsqueda (con o sin resultados).

        QUÉ:
        Normaliza el término buscado, descarta bots, PII y tráfico que supere el rate-limit
        en Redis (por IP hasheada y circuit-breaker global), e incrementa contadores atómicos
        en SearchQuery y SearchQueryDaily.

        POR QUÉ:
        Unifica demanda oculta y consultas con cobertura para rankear por ventana temporal (90d)
        sin almacenar IPs, usuarios ni sesiones, acotando el crecimiento ante flood/scrapers.

        REGLAS Y EFECTOS SECUNDARIOS:
        - Evalúa contains_sensitive_pii() sobre la entrada completa antes de truncar a 100 chars.
        - Nunca interpola el término crudo, IP ni mensaje de excepción en logs.
        - Degradación fail-closed en Redis: si la caché falla, omite la escritura en BD.
        """
        if not keyword or cls.is_bot_user_agent(user_agent):
            return False

        # 1. Evaluar patrones PII sobre la entrada completa antes de truncar
        raw_trimmed = keyword.strip()
        if cls.contains_sensitive_pii(raw_trimmed):
            return False

        # 2. Normalizar espacios internos y acotar a 100 caracteres (mínimo 3)
        clean_keyword = re.sub(r'\s+', ' ', raw_trimmed)[:100].lower()
        if len(clean_keyword) < 3:
            return False

        # 3. Rate limit Nivel 1 por IP hasheada (escrituras totales/min)
        if client_ip and not _skip_write_rate_limit and cls.is_write_rate_limited(client_ip):
            return False

        safe_results = max(0, int(results_count))
        is_matched = safe_results > 0
        matched_delta = 1 if is_matched else 0
        unmatched_delta = 0 if is_matched else 1
        now = timezone.now()
        today = timezone.localdate()

        try:
            # 4. Lookup directo sin SELECT redundante: si ya existe, actualizar directamente
            existing_obj = SearchQuery.objects.filter(query_text=clean_keyword).only('id').first()
            if existing_obj is not None:
                query_obj = existing_obj
                SearchQuery.objects.filter(pk=query_obj.pk).update(
                    search_count=F('search_count') + 1,
                    matched_count=F('matched_count') + matched_delta,
                    unmatched_count=F('unmatched_count') + unmatched_delta,
                    last_results_count=safe_results,
                    last_searched_at=now,
                )
            else:
                # Nivel 2 (términos nuevos por IP) + circuit-breaker global ante rotación multi-IP
                if client_ip:
                    ip_hash = cls._hash_client_ip(client_ip)
                    new_ip_limit = getattr(
                        settings,
                        'SEARCH_TELEMETRY_MAX_NEW_TERMS_PER_10M',
                        cls.SEARCH_TELEMETRY_MAX_NEW_TERMS_PER_10M,
                    )
                    if cls._is_rate_limited(
                        f"store:sq_rl:new_terms:{ip_hash}",
                        new_ip_limit,
                        cls.SEARCH_TELEMETRY_NEW_TERMS_WINDOW_SEC,
                        "new_terms",
                    ):
                        return False

                    global_limit = getattr(
                        settings,
                        'SEARCH_TELEMETRY_GLOBAL_MAX_NEW_TERMS_PER_10M',
                        cls.SEARCH_TELEMETRY_GLOBAL_MAX_NEW_TERMS_PER_10M,
                    )
                    if cls._is_rate_limited(
                        "store:sq_rl:global_new_terms",
                        global_limit,
                        cls.SEARCH_TELEMETRY_NEW_TERMS_WINDOW_SEC,
                        "global_new_terms",
                    ):
                        return False

                try:
                    query_obj, created = SearchQuery.objects.get_or_create(
                        query_text=clean_keyword,
                        defaults={
                            'search_count': 1,
                            'matched_count': matched_delta,
                            'unmatched_count': unmatched_delta,
                            'last_results_count': safe_results,
                        },
                    )
                except IntegrityError:
                    query_obj = SearchQuery.objects.get(query_text=clean_keyword)
                    created = False

                if not created:
                    SearchQuery.objects.filter(pk=query_obj.pk).update(
                        search_count=F('search_count') + 1,
                        matched_count=F('matched_count') + matched_delta,
                        unmatched_count=F('unmatched_count') + unmatched_delta,
                        last_results_count=safe_results,
                        last_searched_at=now,
                    )

            # 5. Upsert atómico en SearchQueryDaily para ranking por ventana temporal
            try:
                daily_obj, daily_created = SearchQueryDaily.objects.get_or_create(
                    search_query=query_obj,
                    date=today,
                    defaults={
                        'matched_count': matched_delta,
                        'unmatched_count': unmatched_delta,
                        'last_results_count': safe_results,
                    },
                )
            except IntegrityError:
                daily_obj = SearchQueryDaily.objects.get(search_query=query_obj, date=today)
                daily_created = False

            if not daily_created:
                SearchQueryDaily.objects.filter(pk=daily_obj.pk).update(
                    matched_count=F('matched_count') + matched_delta,
                    unmatched_count=F('unmatched_count') + unmatched_delta,
                    last_results_count=safe_results,
                )

            logger.info(
                "Consulta de búsqueda registrada de forma agregada (longitud: %d, con_resultados: %s)",
                len(clean_keyword),
                is_matched,
            )
            return True
        except Exception as e:
            logger.error("Error al registrar consulta de búsqueda (tipo de error: %s)", type(e).__name__)
            return False

    @classmethod
    def record_unmatched_search(
        cls,
        keyword: str,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> bool:
        """Wrapper retrocompatible para registrar búsquedas sin resultados."""
        return cls.record_search_query(
            keyword,
            results_count=0,
            user_agent=user_agent,
            client_ip=client_ip,
        )

    @classmethod
    def resolve_period_days(cls, raw_period: Optional[str]) -> Optional[int]:
        """Normaliza el parámetro de ventana temporal; por defecto retorna 90 días."""
        if raw_period is None:
            return cls.DEFAULT_EXPORT_PERIOD_DAYS
        normalized = str(raw_period).strip().lower()
        if normalized in cls.ALLOWED_PERIOD_DAYS:
            return cls.ALLOWED_PERIOD_DAYS[normalized]
        return cls.DEFAULT_EXPORT_PERIOD_DAYS

    @classmethod
    def apply_period_ranking(
        cls,
        queryset: QuerySet,
        period_days: Optional[int] = DEFAULT_EXPORT_PERIOD_DAYS,
    ) -> QuerySet:
        """
        Anota el queryset de SearchQuery con los conteos del período seleccionado.

        # POR QUÉ:
        # Filtrar únicamente por daily_stats__date__gte sin otros JOINs M2M permite que
        # el GROUP BY sobre SearchQuery.id sume cada día del rango sin producto cartesiano.
        """
        if period_days is not None:
            cutoff_date = timezone.localdate() - timedelta(days=period_days)
            return (
                queryset.filter(daily_stats__date__gte=cutoff_date)
                .annotate(
                    period_matched=Coalesce(Sum('daily_stats__matched_count'), Value(0), output_field=IntegerField()),
                    period_unmatched=Coalesce(Sum('daily_stats__unmatched_count'), Value(0), output_field=IntegerField()),
                )
                .annotate(
                    period_total=F('period_matched') + F('period_unmatched'),
                )
            )

        return queryset.annotate(
            period_matched=F('matched_count'),
            period_unmatched=F('unmatched_count'),
            period_total=F('search_count'),
        )

    @staticmethod
    def _classify_suggested_action(last_results_count: int, period_total: int) -> str:
        """Heurística simple para orientar decisiones de Compras o SEO en el Excel."""
        if last_results_count == 0:
            if period_total >= 5:
                return "Incorporar producto / sinónimo prioritario"
            return "Evaluar demanda oculta"
        if last_results_count <= 3:
            return "Ampliar surtido / revisar ficha"
        return "Posicionar SEO / destacar en catálogo"

    @classmethod
    def export_search_queries_workbook(
        cls,
        queryset: Optional[QuerySet] = None,
        period_days: Optional[int] = DEFAULT_EXPORT_PERIOD_DAYS,
        status_filter: str = 'all',
        search_term: str = '',
    ) -> tempfile.SpooledTemporaryFile:
        """
        Exporta el ranking de consultas de búsqueda (con y sin resultados) a Excel (.xlsx) en streaming.

        QUÉ:
        Genera un archivo Excel de 2 hojas ('Ranking' con autofiltro y 'Resumen' con KPIs)
        ordenado por volumen del período elegido (90 días por defecto).

        POR QUÉ:
        Usa openpyxl en modo write_only + .values().iterator(chunk_size=1000) + SpooledTemporaryFile
        para mantener consumo plano de RAM, preservando medidas técnicas ('1/4', '3/8') como
        texto '@' y neutralizando Formula Injection (CWE-1236).
        """
        if queryset is None:
            qs = SearchQuery.objects.all()
            if status_filter == 'unmatched':
                qs = qs.filter(last_results_count=0)
            elif status_filter == 'matched':
                qs = qs.filter(last_results_count__gt=0)
            if search_term and search_term.strip():
                qs = qs.filter(query_text__icontains=search_term.strip())
            qs = cls.apply_period_ranking(qs, period_days=period_days)
        else:
            qs = queryset
            if 'period_total' not in qs.query.annotations:
                qs = cls.apply_period_ranking(qs, period_days=period_days)

        qs = qs.order_by('-period_total', '-last_searched_at')

        wb = openpyxl.Workbook(write_only=True)
        styles = ProductService._get_excel_styles()

        # Hoja 1: Ranking
        ws1 = wb.create_sheet(title="Ranking")
        ws1.views.sheetView[0].showGridLines = True
        ws1.freeze_panes = "A2"
        ws1.auto_filter.ref = "A1:K1"
        ws1.row_dimensions[1].height = 26

        columns = [
            ('ranking', 10),
            ('termino_buscado', 38),
            ('estado_actual', 18),
            ('busquedas_periodo', 18),
            ('sin_resultado_periodo', 22),
            ('con_resultado_periodo', 22),
            ('tasa_sin_resultado', 20),
            ('resultados_actuales', 20),
            ('total_historico', 18),
            ('accion_sugerida', 38),
            ('ultima_busqueda', 20),
        ]
        for col_idx, (_, width) in enumerate(columns, 1):
            col_letter = get_column_letter(col_idx)
            ws1.column_dimensions[col_letter].width = width
        ws1.column_dimensions['B'].number_format = '@'

        ProductService._append_styled_row(
            ws1,
            1,
            [
                (
                    col_name,
                    {
                        'font': styles['font_header'],
                        'fill': styles['fill_navy'],
                        'alignment': styles['align_center'],
                        'border': styles['border_thin'],
                    },
                )
                for col_name, _ in columns
            ],
            write_only=True,
            height=26,
        )

        # Incluir 'id' en .values() para compatibilidad con ONLY_FULL_GROUP_BY en MariaDB 11.
        rows_iter = qs.values(
            'id',
            'query_text',
            'last_results_count',
            'search_count',
            'last_searched_at',
            'period_total',
            'period_unmatched',
            'period_matched',
        ).iterator(chunk_size=1000)

        total_terms = 0
        total_searches = 0
        total_matched = 0
        total_unmatched = 0
        terms_without_results = 0
        terms_with_results = 0

        for idx, row in enumerate(rows_iter, 1):
            period_total = int(row.get('period_total') or 0)
            period_unmatched = int(row.get('period_unmatched') or 0)
            period_matched = int(row.get('period_matched') or 0)
            last_results = int(row.get('last_results_count') or 0)
            total_hist = int(row.get('search_count') or 0)

            total_terms += 1
            total_searches += period_total
            total_matched += period_matched
            total_unmatched += period_unmatched
            if last_results > 0:
                terms_with_results += 1
                estado_label = "Con resultados"
            else:
                terms_without_results += 1
                estado_label = "Sin resultados"

            unmatched_rate = round(period_unmatched / period_total, 4) if period_total > 0 else 0.0
            last_dt = row.get('last_searched_at')
            if last_dt is not None:
                if timezone.is_aware(last_dt):
                    last_dt = timezone.localtime(last_dt)
                last_dt_str = last_dt.strftime('%Y-%m-%d %H:%M')
            else:
                last_dt_str = ''

            term_cell = ProductService._create_write_only_cell(
                ws1,
                row.get('query_text') or '',
                number_format='@',
            )
            term_cell.data_type = 's'

            ws1.append([
                ProductService._create_write_only_cell(ws1, idx, alignment=styles['align_center']),
                term_cell,
                estado_label,
                ProductService._create_write_only_cell(ws1, period_total, number_format='#,##0'),
                ProductService._create_write_only_cell(ws1, period_unmatched, number_format='#,##0'),
                ProductService._create_write_only_cell(ws1, period_matched, number_format='#,##0'),
                ProductService._create_write_only_cell(ws1, unmatched_rate, number_format='0.0%'),
                ProductService._create_write_only_cell(ws1, last_results, number_format='#,##0'),
                ProductService._create_write_only_cell(ws1, total_hist, number_format='#,##0'),
                cls._classify_suggested_action(last_results, period_total),
                last_dt_str,
            ])

        # Hoja 2: Resumen Ejecutivo
        ws2 = wb.create_sheet(title="Resumen")
        ws2.views.sheetView[0].showGridLines = True
        ws2.column_dimensions['A'].width = 36
        ws2.column_dimensions['B'].width = 48

        period_label = f"Últimos {period_days} días" if period_days is not None else "Todo el histórico"
        status_labels = {
            'unmatched': "Solo sin resultados (0 productos)",
            'matched': "Solo con resultados (>= 1 producto)",
            'all': "Todos (con y sin resultados)",
        }
        status_label = status_labels.get(status_filter or 'all', "Todos (con y sin resultados)")
        zero_rate = (total_unmatched / total_searches * 100.0) if total_searches > 0 else 0.0
        clean_search_term = (search_term or '').strip()

        r = 1
        r = ProductService._append_styled_row(
            ws2, r, [("RESUMEN DE CONSULTAS DE BÚSQUEDA", {'font': styles['font_title']})], write_only=True
        )
        r = ProductService._append_styled_row(
            ws2, r, [("Bulonera Alvear — Analítica de Demanda y Posicionamiento SEO", {'font': styles['font_subtitle']})], write_only=True
        )
        r = ProductService._append_styled_row(ws2, r, [], write_only=True)

        summary_rows = [
            ("Fecha de exportación", timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')),
            ("Ventana analizada", period_label),
            ("Filtro de cobertura", status_label),
            ("Filtro de texto", clean_search_term if clean_search_term else "Ninguno"),
            ("Términos únicos exportados", total_terms),
            ("Búsquedas totales del período", total_searches),
            ("Búsquedas con resultado", total_matched),
            ("Búsquedas sin resultado", total_unmatched),
            ("Tasa sin resultado (Zero-Result Rate)", f"{zero_rate:.1f}%"),
            ("Términos actualmente sin cobertura", terms_without_results),
            ("Términos actualmente con cobertura", terms_with_results),
        ]
        for label, val in summary_rows:
            r = ProductService._append_styled_row(
                ws2,
                r,
                [
                    (label, {'font': styles['font_bold'], 'fill': styles['fill_light_gray'], 'border': styles['border_thin']}),
                    (val, {'font': styles['font_regular'], 'border': styles['border_thin']}),
                ],
                write_only=True,
            )

        r = ProductService._append_styled_row(ws2, r, [], write_only=True)
        r = ProductService._append_styled_row(
            ws2, r, [("Guía rápida de acción", {'font': styles['font_bold']})], write_only=True
        )
        guide_rows = [
            ("Compras / Carga de catálogo", "Filtrar 'estado_actual = Sin resultados' en la hoja Ranking y priorizar términos con mayor 'busquedas_periodo'."),
            ("SEO / Posicionamiento", "Filtrar 'estado_actual = Con resultados' y cruzar los términos líderes con Google Search Console para mejorar títulos, fichas y Home."),
            ("Baja cobertura (1 a 3 SKUs)", "Revisar sinónimos o ampliar medidas disponibles en subcategorías con demanda recurrente."),
        ]
        for topic, guide in guide_rows:
            r = ProductService._append_styled_row(
                ws2,
                r,
                [
                    (topic, {'font': styles['font_bold'], 'border': styles['border_thin']}),
                    (guide, {'font': styles['font_regular'], 'alignment': styles['align_wrap'], 'border': styles['border_thin']}),
                ],
                write_only=True,
            )

        tmp_file = tempfile.SpooledTemporaryFile(
            max_size=10 * 1024 * 1024,
            prefix='bulonera_search_queries_',
            suffix='.xlsx',
        )
        wb.save(tmp_file)
        tmp_file.seek(0)
        return tmp_file


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
        """Obtiene datos para feed de Facebook (optimizado con chunks y select_related)"""
        products = Product.objects.filter(is_available=True).select_related('category').iterator(chunk_size=200)
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
        """Obtiene datos para feed de Google Merchant (optimizado con select_related y prefetch_related)."""
        # PERF: prefetch_related evita N+1 queries al acceder a productgallery_set
        # dentro de get_merchant_data(). Sin prefetch, cada producto ejecutaría una
        # consulta adicional a store_productgallery (potencial timeout en catálogos grandes).
        # SUPOSICIÓN: El catálogo actual es <1k productos; omitir iterator() es seguro porque
        # iterator() ignora prefetch_related en Django.
        products = (
            Product.objects.filter(is_available=True)
            .select_related('category')
            .prefetch_related('productgallery_set', 'productgallery_set__image_asset')
        )
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

        elif section.section_type == 'cta_band':
            return {'cta_text': section.cta_text or section.title or ''}

        return {}

    @staticmethod
    def _resolve_products(section, request=None) -> List[Product]:
        """
        Resuelve los productos de un carrusel.
        PRIORIDAD: Manual (HomeSectionProduct) > Auto (source_type)
        """
        from store.models import HomeSectionProduct

        def valid_products(products, limit):
            if limit <= 0:
                return []
            selected = []
            seen_ids = set()
            for product in products:
                if product.id in seen_ids:
                    continue
                if (product.is_available and product.has_valid_price
                        and product.has_valid_image):
                    seen_ids.add(product.id)
                    selected.append(product)
                    if len(selected) >= limit:
                        break
            return selected

        # 1. Los productos manuales conservan prioridad y orden.
        manual_products = section.home_section_products.select_related(
            'product', 'product__image'
        ).order_by('position')
        if manual_products.exists():
            return valid_products(
                (section_product.product for section_product in manual_products),
                section.max_products,
            )

        # 2. Construir candidatos automáticos con los mismos criterios de precio
        # y nombre de archivo; la existencia real se confirma en valid_products.
        limit = section.max_products
        source = section.source_type

        image_query = (
            (Q(image__isnull=False) & ~Q(image__file='') & Q(image__file__isnull=False)) |
            (~Q(images='') & Q(images__isnull=False))
        )
        price_query = (
            Q(is_on_sale=True, sale_price__gt=0) |
            Q(is_on_sale=False, price__gt=0)
        )
        base_qs = Product.objects.filter(
            image_query, price_query, is_available=True
        ).select_related('image')

        if source == 'bestsellers':
            candidates = base_qs.filter(
                orderproduct__isnull=False
            ).annotate(
                order_count=Sum('orderproduct__quantity')
            ).order_by('-order_count')

        elif source == 'most_searched':
            # POR QUÉ: Agrupar por producto y sumar búsquedas de todas las sesiones/usuarios.
            # REGLA: Usar INNER JOIN (productsearch__isnull=False) para evitar filesort en disco de todo el catálogo.
            candidates = base_qs.filter(
                productsearch__isnull=False
            ).annotate(
                total_searches=Sum('productsearch__search_count')
            ).order_by('-total_searches', '-id')

        elif source == 'by_category' and section.category:
            candidates = base_qs.filter(category=section.category).order_by('-sold_count')

        elif source == 'on_sale':
            candidates = base_qs.filter(is_on_sale=True).order_by('-discount_percentage')

        elif source == 'newest':
            candidates = base_qs.order_by('-created_date')
        else:
            return []

        return valid_products(candidates.iterator(chunk_size=50), limit)

    @staticmethod
    def get_recommended_products(section) -> List[Product]:
        """
        Genera la lista de productos recomendados para una sección.
        Se usa para la acción admin 'sugerir productos'.
        """
        return HomeSectionService._resolve_products(section)


class RelatedProductService:
    """
    Motor de recomendación cruzada (cross-selling) para la ficha de producto.

    # QUÉ:
    # Resuelve productos complementarios a partir de `related_subcategories`,
    # `diameter_relation` y `thread_formats_relation`, aplicando Opción C
    # (match técnico indexado) o Opción B (subcategoría libre) según corresponda.
    #
    # POR QUÉ:
    # Evita mantener relaciones manuales producto a producto en +14.000 SKUs,
    # prescinde de `length` (que rompe cruces bulón->tuerca/arandela) y nunca
    # degrada a medidas incompatibles cuando el operador definió medidas técnicas.
    """

    CACHE_KEY_PREFIX = 'store:related_products:v1'
    CACHE_TTL = 900  # 15 minutos

    @staticmethod
    def parse_diameter_and_pitch(raw: Optional[str]) -> Tuple[str, str]:
        return parse_diameter_and_pitch(raw)

    @staticmethod
    def normalize_thread_format(raw: Optional[str]) -> Tuple[str, str]:
        return normalize_thread_format(raw)

    @classmethod
    def invalidate_cache(cls, product_id: Optional[int]) -> None:
        """Elimina la entrada cacheada en Redis para un producto."""
        if product_id:
            cache.delete(f"{cls.CACHE_KEY_PREFIX}:{product_id}")

    @staticmethod
    def _build_valid_price_query() -> Q:
        return Q(is_on_sale=True, sale_price__gt=0) | Q(is_on_sale=False, price__gt=0)

    @classmethod
    def _hydrate_cached_entries(cls, entries: List[Dict], limit: int) -> List[Dict]:
        """
        Hidrata IDs cacheados re-validando disponibilidad, stock y precio vigentes.

        REGLA: Aunque el cálculo de recomendación esté cacheado 15 min en Redis,
        si un producto se quedó sin stock o cambió de precio vía bulk_update se filtra
        en esta única consulta fresca antes de renderizar.
        """
        if not entries:
            return []

        ids = [entry['id'] for entry in entries if 'id' in entry]
        if not ids:
            return []

        products_map = {
            p.id: p
            for p in Product.objects.filter(
                cls._build_valid_price_query(),
                id__in=ids,
                is_available=True,
                stock__gt=0,
            ).select_related('image', 'category')
        }

        hydrated = []
        for entry in entries:
            prod = products_map.get(entry.get('id'))
            if prod is None:
                continue
            hydrated.append({
                'product': prod,
                'badge': entry.get('badge', ''),
                'match_level': entry.get('match_level', 'subcategory'),
            })
            if len(hydrated) >= limit:
                break
        return hydrated

    @staticmethod
    def _parse_relation_criteria(product: Product) -> Tuple[List[str], Optional[str], List[str]]:
        """Extrae diámetros nominales, familia de rosca y pasos esperados del producto."""
        target_diameters: List[str] = []
        target_pitches: List[str] = []

        raw_diameters = getattr(product, 'diameter_relation', '') or ''
        for token in raw_diameters.split(','):
            token = token.strip()
            if not token:
                continue
            diam_nom, diam_pitch = parse_diameter_and_pitch(token)
            if diam_nom and diam_nom not in target_diameters:
                target_diameters.append(diam_nom)
            if diam_pitch and diam_pitch not in target_pitches:
                target_pitches.append(diam_pitch)

        raw_thread = getattr(product, 'thread_formats_relation', '') or ''
        thread_family, thread_pitch = normalize_thread_format(raw_thread)
        if thread_pitch and thread_pitch not in target_pitches:
            target_pitches.append(thread_pitch)

        return target_diameters, (thread_family or None), target_pitches

    @staticmethod
    def _build_technical_badge(
        candidate: Product,
        has_thread_criteria: bool,
    ) -> str:
        """Genera un badge técnico veraz según lo que efectivamente coincide."""
        diam_label = (candidate.diameter_nominal or '').upper()
        has_candidate_thread = bool(candidate.thread_normalized or candidate.thread_pitch)

        if diam_label and has_thread_criteria and has_candidate_thread:
            thread_label = candidate.thread_formats or (
                f"P {candidate.thread_pitch}" if candidate.thread_pitch else candidate.thread_normalized.upper()
            )
            full_label = f"Compatible {diam_label} · {thread_label}"
            if len(full_label) > 32:
                short_thread = (
                    f"P {candidate.thread_pitch}" if candidate.thread_pitch else candidate.thread_normalized.upper()
                )
                return f"Compatible {diam_label} · {short_thread}"[:32]
            return full_label

        if diam_label:
            return f"Medida {diam_label}"[:32]

        thread_label = candidate.thread_formats or candidate.thread_normalized.upper()
        return f"Rosca {thread_label}"[:32] if thread_label else "Compatible"

    @classmethod
    def get_related_products(cls, product: Product, limit: int = 6) -> List[Dict]:
        """
        Retorna hasta `limit` productos complementarios para la ficha de `product`.

        # CÓMO:
        # 1. Consulta Redis; si hay hit, hidrata con stock/precio frescos.
        # 2. Si no hay `related_subcategories`, cachea [] y retorna [].
        # 3. Si `diameter_relation` o `thread_formats_relation` tienen valor, aplica Opción C
        #    por subcategoría (omitiendo la subcategoría si no hay stock compatible).
        # 4. Si ambos están vacíos, aplica Opción B (mejores con stock de la subcategoría).
        # 5. Combina resultados en round-robin para garantizar variedad entre subcategorías.
        """
        if not product or not product.pk or limit <= 0:
            return []

        cache_key = f"{cls.CACHE_KEY_PREFIX}:{product.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cls._hydrate_cached_entries(cached, limit)

        related_subcats = list(product.related_subcategories.all().order_by('id'))
        if not related_subcats:
            cache.set(cache_key, [], cls.CACHE_TTL)
            return []

        target_diameters, target_thread_family, target_pitches = cls._parse_relation_criteria(product)
        is_technical_mode = bool(target_diameters or target_thread_family or target_pitches)
        has_thread_criteria = bool(target_thread_family or target_pitches)

        price_query = cls._build_valid_price_query()
        has_img_expr = Case(
            When(Q(image__isnull=False) | ~Q(images=''), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )

        per_subcat_queues: List[List[Dict]] = []
        source_material = (product.material or '').strip()

        for subcat in related_subcats:
            qs = (
                Product.objects.filter(
                    price_query,
                    subcategories=subcat,
                    is_available=True,
                    stock__gt=0,
                )
                .exclude(id=product.pk)
                .select_related('image', 'category')
            )

            if is_technical_mode:
                if target_diameters:
                    qs = qs.filter(diameter_nominal__in=target_diameters)
                if target_thread_family:
                    allowed_families = COMPATIBLE_THREAD_FAMILIES.get(
                        target_thread_family, {target_thread_family}
                    )
                    # REGLA: Candidatos sin rosca (ej. Arandelas) nunca se excluyen por filtro de rosca.
                    qs = qs.filter(
                        Q(thread_normalized='', thread_pitch='')
                        | Q(thread_normalized__in=allowed_families)
                    )
                if target_pitches:
                    qs = qs.filter(
                        Q(thread_pitch='') | Q(thread_pitch__in=target_pitches)
                    )

            qs = qs.annotate(has_img_priority=has_img_expr)
            if source_material:
                qs = qs.annotate(
                    same_material=Case(
                        When(material__iexact=source_material, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ).order_by('-has_img_priority', '-same_material', '-sold_count', '-is_on_sale', 'id')
            else:
                qs = qs.order_by('-has_img_priority', '-sold_count', '-is_on_sale', 'id')

            candidates = list(qs.distinct()[:limit])
            if not candidates:
                # REGLA: En Opción C, si no hay stock compatible se omite la subcategoría
                # para no recomendar una medida incompatible.
                continue

            queue: List[Dict] = []
            for cand in candidates:
                badge = (
                    cls._build_technical_badge(cand, has_thread_criteria)
                    if is_technical_mode
                    else subcat.subcategory_name
                )
                queue.append({
                    'product': cand,
                    'badge': badge,
                    'match_level': 'technical' if is_technical_mode else 'subcategory',
                })
            per_subcat_queues.append(queue)

        # Round-robin entre subcategorías para mostrar variedad (tuerca + arandela, etc.).
        selected: List[Dict] = []
        seen_ids = set()
        idx = 0
        while len(selected) < limit and per_subcat_queues:
            progressed = False
            for queue in per_subcat_queues:
                while idx < len(queue) and queue[idx]['product'].id in seen_ids:
                    # Avanzar dentro de esta cola si el producto ya fue agregado por otra subcat
                    queue.pop(idx)
                if idx < len(queue):
                    item = queue[idx]
                    seen_ids.add(item['product'].id)
                    selected.append(item)
                    progressed = True
                    if len(selected) >= limit:
                        break
            if not progressed:
                break
            idx += 1

        cache_payload = [
            {
                'id': item['product'].id,
                'badge': item['badge'],
                'match_level': item['match_level'],
            }
            for item in selected
        ]
        cache.set(cache_key, cache_payload, cls.CACHE_TTL)
        return selected


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
    'RelatedProductService',
]

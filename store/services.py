"""
Store App Services

Contiene la lógica de negocio pura para gestión de productos, búsqueda, reviews y FAQs.
"""
import logging
import os
import io
import re
import uuid
import zlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import pandas as pd
from django.db.models import Q, QuerySet, Avg, Count, Sum
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
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

    # Especificación canónica de las 30 columnas del importador masivo
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

    @classmethod
    def generate_import_template_workbook(cls, mode: str = 'full') -> io.BytesIO:
        """
        Genera en memoria un archivo Excel (.xlsx) estructurado y formateado
        para la carga masiva de productos o actualización rápida de precios.

        # POR QUÉ:
        # Los operadores de Django Admin necesitan una plantilla con las 30 columnas
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

        fill_green = PatternFill(start_color="166534", end_color="166534", fill_type="solid")
        fill_navy = PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid")
        fill_slate = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        fill_blue = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
        fill_light_gray = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        font_title = Font(name="Calibri", size=14, bold=True, color="1B3A5C")
        font_subtitle = Font(name="Calibri", size=11, italic=True, color="475569")
        font_bold = Font(name="Calibri", size=11, bold=True, color="1E293B")
        font_regular = Font(name="Calibri", size=11, color="334155")

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        if mode == 'prices':
            ws1 = wb.active
            ws1.title = "Lista_Precios"
            ws1.views.sheetView[0].showGridLines = True
            ws1.freeze_panes = "A2"
            ws1.row_dimensions[1].height = 28

            headers = ['code', 'price']
            for col_idx, h in enumerate(headers, 1):
                cell = ws1.cell(row=1, column=col_idx, value=h)
                cell.font = font_header
                cell.fill = fill_green
                cell.alignment = align_center
                cell.border = border_thin
                col_letter = get_column_letter(col_idx)
                ws1.column_dimensions[col_letter].width = 20
                if h == 'code':
                    ws1.column_dimensions[col_letter].number_format = '@'

            ws2 = wb.create_sheet(title="Instrucciones")
            ws2.views.sheetView[0].showGridLines = True
            ws2.append(["INSTRUCCIONES PARA ACTUALIZACIÓN RÁPIDA DE PRECIOS"])
            ws2.cell(row=1, column=1).font = font_title
            ws2.append(["Bulonera Alvear - Gestión Administrativa"])
            ws2.cell(row=2, column=1).font = font_subtitle
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
                c1.font = font_bold
                c2 = ws2.cell(row=r, column=2, value=desc)
                c2.font = font_regular

            ws2.column_dimensions['A'].width = 25
            ws2.column_dimensions['B'].width = 85

        else:
            ws1 = wb.active
            ws1.title = "Productos"
            ws1.views.sheetView[0].showGridLines = True
            ws1.freeze_panes = "A2"
            ws1.row_dimensions[1].height = 28

            for col_idx, col_spec in enumerate(cls.IMPORT_TEMPLATE_COLUMNS, 1):
                h_name = col_spec['name']
                cell = ws1.cell(row=1, column=col_idx, value=h_name)
                cell.font = font_header
                cell.alignment = align_center
                cell.border = border_thin

                grp = col_spec['group']
                if grp == 'required':
                    cell.fill = fill_green
                elif grp == 'catalog':
                    cell.fill = fill_navy
                elif grp == 'tech':
                    cell.fill = fill_slate
                else:
                    cell.fill = fill_blue

                col_letter = get_column_letter(col_idx)
                if col_spec.get('format') == '@':
                    ws1.column_dimensions[col_letter].number_format = '@'
                ws1.column_dimensions[col_letter].width = max(len(h_name) + 5, 14)

            col_names = [c['name'] for c in cls.IMPORT_TEMPLATE_COLUMNS]

            if 'condition' in col_names:
                c_idx = col_names.index('condition') + 1
                c_letter = get_column_letter(c_idx)
                dv_cond = DataValidation(type="list", formula1='"new,used,refurbished"', allow_blank=True)
                dv_cond.error = 'Selecciona un valor válido: new, used, refurbished'
                dv_cond.errorTitle = 'Condición no válida'
                ws1.add_data_validation(dv_cond)
                dv_cond.add(f"{c_letter}2:{c_letter}2000")

            if 'tax_rate' in col_names:
                t_idx = col_names.index('tax_rate') + 1
                t_letter = get_column_letter(t_idx)
                dv_tax = DataValidation(type="list", formula1='"21.00,10.50,0.00"', allow_blank=True)
                dv_tax.error = 'Selecciona una alícuota válida: 21.00, 10.50 o 0.00'
                dv_tax.errorTitle = 'Alícuota IVA no válida'
                ws1.add_data_validation(dv_tax)
                dv_tax.add(f"{t_letter}2:{t_letter}2000")

            ws2 = wb.create_sheet(title="Guía y Ejemplos")
            ws2.views.sheetView[0].showGridLines = True

            ws2.append(["GUÍA DE CAMPOS PARA IMPORTACIÓN MASIVA DE PRODUCTOS"])
            ws2.cell(row=1, column=1).font = font_title
            ws2.append(["Bulonera Alvear - Plantilla Oficial de Carga"])
            ws2.cell(row=2, column=1).font = font_subtitle
            ws2.append([])

            ws2.append(["Explicación de Colores en la Hoja 'Productos':"])
            ws2.cell(row=4, column=1).font = font_bold

            legend_items = [
                ("Verde", "Campos obligatorios requeridos para todo producto (code y price).", fill_green),
                ("Azul Marino", "Datos del catálogo comercial e impositivos (categoría, stock, IVA Res. 4/2025, tags, imágenes).", fill_navy),
                ("Acero / Gris", "Dimensiones y especificaciones técnicas para bulonería y ferretería (diámetro, largo, norma, grado).", fill_slate),
                ("Azul Claro", "Identificadores universales EAN/MPN, categorización de Google, SEO y FAQs.", fill_blue),
            ]
            for color_name, desc, fill in legend_items:
                r = ws2.max_row + 1
                c1 = ws2.cell(row=r, column=1, value=color_name)
                c1.fill = fill
                c1.font = font_header
                c1.alignment = align_center
                c1.border = border_thin
                c2 = ws2.cell(row=r, column=2, value=desc)
                c2.font = font_regular
                c2.alignment = align_left

            ws2.append([])
            ws2.append(["Regla de Nombres Automáticos:"])
            ws2.cell(row=ws2.max_row, column=1).font = font_bold
            ws2.append(["Si un producto incluye 'diameter' y 'length', y su 'name' no contiene las medidas, el sistema genera automáticamente: {nombre} {diámetro} x {longitud}."])
            ws2.cell(row=ws2.max_row, column=1).font = font_regular
            ws2.append([])

            table_header_row = ws2.max_row + 1
            guide_headers = ["Columna", "Obligatorio", "Tipo de Dato", "Regla de Negocio / Valor por Defecto"]
            for c_idx, gh in enumerate(guide_headers, 1):
                cell = ws2.cell(row=table_header_row, column=c_idx, value=gh)
                cell.font = font_header
                cell.fill = fill_navy
                cell.alignment = align_center
                cell.border = border_thin
            ws2.row_dimensions[table_header_row].height = 24

            for col_spec in cls.IMPORT_TEMPLATE_COLUMNS:
                r = ws2.max_row + 1
                c1 = ws2.cell(row=r, column=1, value=col_spec['name'])
                c1.font = font_bold
                c1.alignment = align_left
                c1.border = border_thin

                req_text = "SÍ (Obligatorio)" if col_spec['required'] else "Opcional"
                c2 = ws2.cell(row=r, column=2, value=req_text)
                c2.font = font_bold if col_spec['required'] else font_regular
                c2.alignment = align_center
                c2.border = border_thin
                if col_spec['required']:
                    c2.fill = fill_light_gray

                c3 = ws2.cell(row=r, column=3, value=col_spec['type_desc'])
                c3.font = font_regular
                c3.alignment = align_left
                c3.border = border_thin

                c4 = ws2.cell(row=r, column=4, value=col_spec['rule'])
                c4.font = font_regular
                c4.alignment = align_left
                c4.border = border_thin

            ws2.append([])
            ws2.append(["EJEMPLOS PRÁCTICOS DE CARGA (3 CASOS REALES)"])
            ws2.cell(row=ws2.max_row, column=1).font = font_title
            ws2.append(["Puedes consultar y copiar estos ejemplos para familiarizarte con los formatos:"])
            ws2.cell(row=ws2.max_row, column=1).font = font_subtitle
            ws2.append([])

            ex_header_row = ws2.max_row + 1
            for c_idx, col_spec in enumerate(cls.IMPORT_TEMPLATE_COLUMNS, 1):
                cell = ws2.cell(row=ex_header_row, column=c_idx, value=col_spec['name'])
                cell.font = font_header
                cell.fill = fill_slate
                cell.alignment = align_center
                cell.border = border_thin
            ws2.row_dimensions[ex_header_row].height = 22

            sample_keys = ['sample_1', 'sample_2', 'sample_3']
            for s_key in sample_keys:
                r = ws2.max_row + 1
                for c_idx, col_spec in enumerate(cls.IMPORT_TEMPLATE_COLUMNS, 1):
                    val = col_spec.get(s_key, '')
                    cell = ws2.cell(row=r, column=c_idx, value=val)
                    cell.font = font_regular
                    cell.alignment = align_left
                    cell.border = border_thin

            ws2.column_dimensions['A'].width = 18
            ws2.column_dimensions['B'].width = 18
            ws2.column_dimensions['C'].width = 24
            ws2.column_dimensions['D'].width = 80

            ws3 = wb.create_sheet(title="Guía de Imágenes")
            ws3.views.sheetView[0].showGridLines = True
            ws3.append(["GUÍA DE CARGA Y GESTIÓN DE IMÁGENES"])
            ws3.cell(row=1, column=1).font = font_title
            ws3.append(["Bulonera Alvear - Pipeline WebP y CDN"])
            ws3.cell(row=2, column=1).font = font_subtitle
            ws3.append([])

            img_rules = [
                ("1. Directorio en el Servidor", "Las fotos deben subirse previamente a la carpeta:\nmedia/photos/products/original/\n(a través del panel de Media Bank o SSH/SFTP)."),
                ("2. Formatos Soportados", "Se admiten formatos .jpg, .jpeg, .png y .webp. El servidor optimiza y genera automáticamente las variantes responsivas en WebP."),
                ("3. Nombres de Archivo", "Usar nombres en minúsculas, sin espacios ni caracteres especiales (ej. 'tornillo-hexagonal-m8.jpg')."),
                ("4. Imagen Principal ('images')", "Se especifica el nombre exacto de un único archivo (ej. 'bulon-g2-14112.jpg'). Si el producto ya existe y este campo se deja vacío, conserva la imagen actual."),
                ("5. Galería Secundaria ('gallery')", "Múltiples imágenes separadas por comas SIN espacios (ej. 'foto1.jpg,foto2.jpg,foto3.jpg'). En actualizaciones, si se especifican fotos en este campo, reemplaza la galería anterior."),
                ("6. Preguntas Frecuentes ('faq')", "Se cargan asociadas a la subcategoría en formato:\n\"¿Pregunta 1?\" Respuesta 1, \"¿Pregunta 2?\" Respuesta 2"),
            ]
            for title, desc in img_rules:
                r = ws3.max_row + 1
                c1 = ws3.cell(row=r, column=1, value=title)
                c1.font = font_bold
                c1.alignment = Alignment(horizontal="left", vertical="top")
                c1.border = border_thin
                c2 = ws3.cell(row=r, column=2, value=desc)
                c2.font = font_regular
                c2.alignment = align_wrap
                c2.border = border_thin

            ws3.column_dimensions['A'].width = 30
            ws3.column_dimensions['B'].width = 85

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
    
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
    def start_bulk_upload_session(cls, file_or_path, mode: str, user_id: int) -> dict:
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
            f"Iniciada sesión de carga masiva {upload_id} (modo={mode}, filas={len(data)}, lotes={total_chunks}, usuario={user_id})"
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
            chunk_result = cls._process_import_chunk(rows, chunk_offset)

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
    def _process_import_chunk(cls, rows: list, chunk_offset: int) -> dict:
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
                        result=result, processed_subcategories=processed_subcategories
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
    """Servicio para búsqueda de productos y análisis de telemetría agregada"""
    
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

    @classmethod
    def record_unmatched_search(cls, keyword: str) -> None:
        """
        Registra o incrementa el contador de un término de búsqueda que no arrojó resultados.
        Normaliza el texto y opera de manera atómica sin almacenar IPs, usuarios ni sesiones.
        Aplica filtro heurístico anti-PII por patrones sobre la entrada completa (evita que la truncación
        oculte datos sensibles en el límite de longitud).
        Unifica la normalización con search_products limitando a 100 caracteres.
        Higiene estricta de logs: no interpola el término crudo ni en logs normales ni en logs de error.
        search_count cuantifica volumen de solicitudes fallidas, no demandantes únicos.
        """
        if not keyword:
            return

        # 1. Evaluar patrones PII sobre la entrada completa antes de truncar
        raw_trimmed = keyword.strip()
        if cls.contains_sensitive_pii(raw_trimmed):
            return

        # 2. Normalización idéntica a search_products (límite estricto de 100 caracteres)
        clean_keyword = raw_trimmed[:100].lower()
        if len(clean_keyword) < 3:
            return

        try:
            from store.models import SearchQuery
            from django.db.models import F
            from django.utils import timezone

            query_obj, created = SearchQuery.objects.get_or_create(
                query_text=clean_keyword,
                defaults={'search_count': 1}
            )
            if not created:
                SearchQuery.objects.filter(pk=query_obj.pk).update(
                    search_count=F('search_count') + 1,
                    last_searched_at=timezone.now()
                )
            logger.info("Demanda oculta registrada de forma agregada (longitud: %d caracteres)", len(clean_keyword))
        except Exception as e:
            logger.error("Error al registrar búsqueda sin resultado (tipo de error: %s)", type(e).__name__)


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

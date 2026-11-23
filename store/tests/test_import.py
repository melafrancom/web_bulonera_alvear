"""
Tests para importación de productos desde Excel/CSV
"""
import pytest
import pandas as pd
from decimal import Decimal
from pathlib import Path
from io import BytesIO

from store.services import ProductService, ImportResult
from store.models import Product, ProductGallery, FAQ
from category.models import Category, SubCategory


@pytest.mark.django_db
class TestProductImport:
    """Tests para importación de productos"""
    
    def create_test_excel(self, data: list) -> BytesIO:
        """Crea un archivo Excel de prueba en memoria"""
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        buffer.name = 'test.xlsx'
        return buffer
    
    def test_import_crea_productos(self):
        """Test: Importar productos nuevos los crea correctamente"""
        data = [
            {
                'code': 'TEST001',
                'name': 'Producto Test 1',
                'price': 100.50,
                'stock': 10,
                'category': 'Test Category'
            },
            {
                'code': 'TEST002',
                'name': 'Producto Test 2',
                'price': 200.75,
                'stock': 5,
                'category': 'Test Category'
            }
        ]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 2
        assert result.updated == 0
        assert result.errors == 0
        
        # Verificar que los productos existen
        product1 = Product.objects.get(code='TEST001')
        assert product1.name == 'Producto Test 1'
        assert product1.price == 100.50
        assert product1.stock == 10
        
        product2 = Product.objects.get(code='TEST002')
        assert product2.name == 'Producto Test 2'
        assert product2.price == 200.75
    
    def test_import_actualiza_producto_existente(self):
        """Test: Importar producto existente lo actualiza"""
        # Crear producto inicial
        category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        product = Product.objects.create(
            code='TEST001',
            name='Producto Original',
            price=100.00,
            stock=10,
            category=category
        )
        
        # Importar con datos actualizados
        data = [{
            'code': 'TEST001',
            'name': 'Producto Actualizado',
            'price': 150.00,
            'stock': 20,
            'category': 'Test Category'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 0
        assert result.updated == 1
        assert result.errors == 0
        
        # Verificar actualización
        product.refresh_from_db()
        assert product.name == 'Producto Actualizado'
        assert product.price == 150.00
        assert product.stock == 20
    
    def test_dry_run_no_modifica_bd(self):
        """Test: Dry run no modifica la base de datos"""
        data = [{
            'code': 'TEST001',
            'name': 'Producto Test',
            'price': 100.00,
            'category': 'Test Category'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file, dry_run=True)
        
        assert result.created == 1  # Reporta que crearía 1
        assert result.errors == 0
        
        # Verificar que NO se creó en la BD
        assert not Product.objects.filter(code='TEST001').exists()
    
    def test_column_obligatoria_faltante_cuenta_error(self):
        """Test: Fila sin código o precio genera error"""
        data = [
            {'code': 'TEST001', 'name': 'Producto 1'},  # Falta price
            {'price': 100.00, 'name': 'Producto 2'},    # Falta code
        ]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 0
        assert result.errors == 2
        assert len(result.error_details) == 2
    
    def test_categoria_inexistente_se_crea(self):
        """Test: Categoría que no existe se crea automáticamente"""
        data = [{
            'code': 'TEST001',
            'name': 'Producto Test',
            'price': 100.00,
            'category': 'Nueva Categoría'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 1
        assert result.errors == 0
        
        # Verificar que la categoría se creó
        category = Category.objects.get(category_name='Nueva Categoría')
        assert category.slug == 'nueva-categoria'
        
        product = Product.objects.get(code='TEST001')
        assert product.category == category
    
    def test_update_prices_actualiza_precio(self):
        """Test: Actualización de precios modifica precio y recalcula descuento de ofertas"""
        category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        product = Product.objects.create(
            code='TEST001',
            name='Producto Test',
            price=100.00,
            stock=10,
            category=category,
            is_on_sale=True,
            sale_price=50.00,
            discount_percentage=50
        )
        
        data = [{
            'code': 'TEST001',
            'price': 200.00
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.update_prices_from_file(excel_file)
        
        assert result.updated == 1
        assert result.errors == 0
        
        product.refresh_from_db()
        assert product.price == 200.00
        assert product.discount_percentage == 75
        assert product.name == 'Producto Test'  # No cambió
        assert product.stock == 10  # No cambió

    def test_import_skips_celery_image_task_during_bulk_processing(self, monkeypatch):
        """Test: Carga masiva omite encolar tareas Celery redundantes a redis"""
        from unittest.mock import MagicMock
        mock_delay = MagicMock()
        monkeypatch.setattr('store.tasks.process_product_image.delay', mock_delay)

        category = Category.objects.create(category_name='Cat Celery', slug='cat-celery')
        product = Product.objects.create(
            code='CELERY01',
            name='Producto Con Foto',
            price=100.00,
            stock=10,
            category=category,
            images='photos/products/original/test.jpg'
        )
        # Resetear el mock si la creación previa lo llamó
        mock_delay.reset_mock()

        data = [{
            'code': 'CELERY01',
            'name': 'Producto Con Foto Actualizado',
            'price': 120.00,
            'category': 'Cat Celery'
        }]

        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)

        assert result.updated == 1
        # No debe haber llamado a Celery .delay() durante la importación
        assert mock_delay.call_count == 0
    
    def test_update_prices_codigo_inexistente(self):
        """Test: Actualizar precio de código inexistente genera error"""
        data = [{
            'code': 'NOEXISTE',
            'price': 100.00
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.update_prices_from_file(excel_file)
        
        assert result.updated == 0
        assert result.errors == 1
        assert 'no existe' in result.error_details[0][1].lower()
    
    def test_subcategorias_se_crean_y_asocian(self):
        """Test: Subcategorías se crean y asocian al producto"""
        data = [{
            'code': 'TEST001',
            'name': 'Producto Test',
            'price': 100.00,
            'category': 'Test Category',
            'subcategories': 'Subcat 1, Subcat 2'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 1
        assert result.errors == 0
        
        product = Product.objects.get(code='TEST001')
        subcats = product.subcategories.all()
        
        assert subcats.count() == 2
        assert subcats.filter(subcategory_name='Subcat 1').exists()
        assert subcats.filter(subcategory_name='Subcat 2').exists()
    
    def test_precio_decimal_correcto(self):
        """Test: Los precios se guardan correctamente (FloatField en el modelo actual)"""
        data = [{
            'code': 'TEST001',
            'name': 'Producto Test',
            'price': 99.99,
            'category': 'Test Category'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 1
        
        product = Product.objects.get(code='TEST001')
        # Nota: El modelo usa FloatField, debería ser DecimalField en el futuro
        assert isinstance(product.price, float)
        assert product.price == 99.99
    
    def test_campos_opcionales_se_guardan(self):
        """Test: Campos opcionales se guardan correctamente"""
        data = [{
            'code': 'TEST001',
            'name': 'Producto Test',
            'price': 100.00,
            'category': 'Test Category',
            'brand': 'Test Brand',
            'diameter': '10mm',
            'length': '50mm',
            'material': 'Acero',
            'origin': 'Argentina'
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 1
        
        product = Product.objects.get(code='TEST001')
        assert product.brand == 'Test Brand'
        assert product.diameter == '10mm'
        assert product.length == '50mm'
        assert product.material == 'Acero'
        assert product.origin == 'Argentina'

    def test_import_crea_y_asocia_tags_correctamente(self):
        """Test: Importar productos con columna 'tags' crea ProductTag y asocia M2M."""
        # Arrange
        data = [{
            'code': 'TAGPROD1',
            'name': 'Bulón Cabeza Redonda',
            'price': 150.00,
            'category': 'Fijaciones',
            'tags': 'Acero Inoxidable, Construcción, Destacados'
        }]

        # Act
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)

        # Assert
        assert result.created == 1
        product = Product.objects.get(code='TAGPROD1')
        tags = list(product.tags.values_list('slug', flat=True))
        assert 'acero-inoxidable' in tags
        assert 'construccion' in tags
        assert 'destacados' in tags
        assert len(result.tags_created) == 3

    def test_import_reutiliza_tags_existentes_sin_duplicar(self):
        """Test: Importar productos no duplica ProductTag si el slug ya existe."""
        # Arrange
        from store.models import ProductTag
        ProductTag.objects.create(name="Oferta", slug="oferta")

        data = [{
            'code': 'TAGPROD2',
            'name': 'Tuerca Hexagonal',
            'price': 80.00,
            'category': 'Fijaciones',
            'tags': 'Oferta, Nuevo'
        }]

        # Act
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)

        # Assert
        assert result.created == 1
        assert ProductTag.objects.filter(slug='oferta').count() == 1
        assert ProductTag.objects.filter(slug='nuevo').count() == 1
        assert 'Oferta' not in result.tags_created
        assert 'Nuevo' in result.tags_created

    def test_import_columna_tags_vacia_no_falla(self):
        """Test: Fila con columna tags vacía se importa sin errores y sin tags asignados."""
        # Arrange
        data = [{
            'code': 'TAGPROD3',
            'name': 'Arandela Simple',
            'price': 30.00,
            'category': 'Fijaciones',
            'tags': ''
        }]

        # Act
        excel_file = self.create_test_excel(data)
        result = ProductService.import_from_file(excel_file)

        # Assert
        assert result.created == 1
        product = Product.objects.get(code='TAGPROD3')
        assert product.tags.count() == 0


@pytest.mark.django_db
class TestERPClient:
    """Tests para el stub del ERP Client"""
    
    def test_erp_client_stub_raises_not_implemented(self):
        """Test: ERP Client stub lanza NotImplementedError"""
        from erp_client import ERPClient
        
        client = ERPClient()
        
        with pytest.raises(NotImplementedError):
            client.get_products()
        
        with pytest.raises(NotImplementedError):
            client.get_product('TEST001')
        
        with pytest.raises(NotImplementedError):
            client.get_categories()
    
    def test_erp_client_importable(self):
        """Test: ERP Client es importable"""
        from erp_client import ERPClient, ERPUnavailableError, ERPAuthError
        
        assert ERPClient is not None
        assert ERPUnavailableError is not None
        assert ERPAuthError is not None


@pytest.mark.django_db
class TestImportTemplateGeneration:
    """Tests unitarios y de integración para la generación de plantillas Excel de importación"""

    def test_generate_full_template_structure_and_headers(self):
        """Test: Genera la plantilla completa con 33 columnas canónicas y 3 hojas bien formateadas"""
        import openpyxl
        from openpyxl.utils import get_column_letter

        buffer = ProductService.generate_import_template_workbook(mode='full')
        
        # Validar que es un archivo Excel válido
        wb = openpyxl.load_workbook(buffer, data_only=False)
        assert wb.sheetnames == ['Productos', 'Guía y Ejemplos', 'Guía de Imágenes']
        
        ws1 = wb['Productos']
        # Fila 1 debe tener exactamente las 33 columnas canónicas
        header_row = [cell.value for cell in ws1[1]]
        expected_columns = [col['name'] for col in ProductService.IMPORT_TEMPLATE_COLUMNS]
        assert len(header_row) == 33
        assert header_row == expected_columns
        assert 'related_subcategories' in header_row
        assert 'diameter_relation' in header_row
        assert 'thread_formats_relation' in header_row
        assert 'tax_rate' in header_row
        assert 'tags' in header_row
        assert 'code' in header_row
        assert 'price' in header_row

        # Hoja 1 NO debe tener filas de datos pre-cargadas para evitar crear registros basura
        assert ws1.max_row == 1

        # Paneles inmovilizados
        assert ws1.freeze_panes == 'A2'

        # Formato texto '@' en columnas sensibles
        for col_name in ['code', 'diameter', 'length', 'diameter_relation', 'gtin', 'mpn']:
            col_idx = header_row.index(col_name) + 1
            col_letter = get_column_letter(col_idx)
            assert ws1.column_dimensions[col_letter].number_format == '@'

        # Hoja 2 y 3 deben tener contenido explicativo
        ws2 = wb['Guía y Ejemplos']
        assert ws2.max_row > 10
        ws3 = wb['Guía de Imágenes']
        assert ws3.max_row > 5

    def test_generate_prices_template_structure(self):
        """Test: Genera la plantilla rápida de actualización de precios con 2 columnas"""
        import openpyxl
        buffer = ProductService.generate_import_template_workbook(mode='prices')
        
        wb = openpyxl.load_workbook(buffer, data_only=False)
        assert wb.sheetnames == ['Lista_Precios', 'Instrucciones']
        
        ws1 = wb['Lista_Precios']
        header_row = [cell.value for cell in ws1[1]]
        assert header_row == ['code', 'price']
        assert ws1.max_row == 1
        assert ws1.freeze_panes == 'A2'

    def test_roundtrip_generated_template_imports_cleanly(self):
        """Test round-trip: Escribir datos en la plantilla generada e importarla crea el producto correctamente"""
        import openpyxl
        from store.models import Product, ProductTag

        # 1. Generar plantilla oficial
        template_buffer = ProductService.generate_import_template_workbook(mode='full')
        
        # 2. Abrir con openpyxl y agregar una fila realista
        wb = openpyxl.load_workbook(template_buffer)
        ws = wb['Productos']
        headers = [c.value for c in ws[1]]
        
        row_data = {
            'code': '00100200099',
            'price': '1250.50',
            'name': 'Bulón Cabeza Hexagonal G2 UNC Zincado',
            'diameter': '1/4"',
            'length': '1-1/2"',
            'stock': '300',
            'category': 'Bulonería',
            'subcategories': 'Hexagonales, Grado 2',
            'tags': 'Inoxidable, Industrial',
            'tax_rate': '10.50',
            'brand': 'Bulonera Alvear',
            'condition': 'new',
        }
        
        new_row = [row_data.get(h, '') for h in headers]
        ws.append(new_row)
        
        save_buf = BytesIO()
        wb.save(save_buf)
        save_buf.seek(0)
        save_buf.name = 'template_test.xlsx'
        
        # 3. Importar a través de ProductService
        result = ProductService.import_from_file(save_buf)
        assert result.errors == 0
        assert result.created == 1
        
        # 4. Verificar en base de datos
        product = Product.objects.get(code='00100200099')
        assert product.price == 1250.50
        assert product.tax_rate == Decimal('10.50')
        assert product.category.category_name == 'Bulonería'
        assert product.subcategories.count() == 2
        assert product.tags.count() == 2
        tag_slugs = set(product.tags.values_list('slug', flat=True))
        assert 'inoxidable' in tag_slugs
        assert 'industrial' in tag_slugs

    def test_parse_file_ignores_completely_empty_rows(self):
        """Test: Filas completamente en blanco no generan falsos errores de importación"""
        data = [
            {'code': 'EMPTYROW01', 'name': 'Bulón Normal', 'price': 100.0, 'category': 'General'},
            {'code': None, 'name': None, 'price': None, 'category': None},
            {'code': '', 'name': '', 'price': '', 'category': ''},
        ]
        excel_file = TestProductImport().create_test_excel(data)
        result = ProductService.import_from_file(excel_file)
        
        assert result.created == 1
        assert result.errors == 0
        assert Product.objects.filter(code='EMPTYROW01').exists()


@pytest.mark.django_db
class TestAdminImportTemplateDownload:
    """Tests de integración para el endpoint de descarga en Django Admin"""

    def test_admin_download_full_template_returns_xlsx(self, client, admin_user):
        """Test: Usuario admin puede descargar la plantilla completa en .xlsx"""
        import openpyxl
        from django.urls import reverse

        client.force_login(admin_user)
        url = reverse('admin:store_product_download_import_template')
        response = client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'attachment; filename="plantilla_importacion_productos_bulonera.xlsx"' in response['Content-Disposition']

        # Verificar que el contenido es un Excel válido
        content_bytes = b"".join(response.streaming_content)
        wb = openpyxl.load_workbook(BytesIO(content_bytes))
        assert wb.sheetnames == ['Productos', 'Guía y Ejemplos', 'Guía de Imágenes']

    def test_admin_download_prices_template_returns_xlsx(self, client, admin_user):
        """Test: Usuario admin puede descargar la plantilla de precios con ?mode=prices"""
        import openpyxl
        from django.urls import reverse

        client.force_login(admin_user)
        url = f"{reverse('admin:store_product_download_import_template')}?mode=prices"
        response = client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'attachment; filename="plantilla_actualizar_precios_bulonera.xlsx"' in response['Content-Disposition']

        content_bytes = b"".join(response.streaming_content)
        wb = openpyxl.load_workbook(BytesIO(content_bytes))
        assert wb.sheetnames == ['Lista_Precios', 'Instrucciones']

    def test_anonymous_user_redirected_to_admin_login(self, client):
        """Test: Usuario anónimo es redirigido al login de admin"""
        from django.urls import reverse
        url = reverse('admin:store_product_download_import_template')
        response = client.get(url)
        assert response.status_code == 302
        assert '/admin/login/' in response.url

    def test_staff_without_product_permissions_gets_403(self, client):
        """Test: Usuario staff sin permisos sobre Product recibe 403 Forbidden"""
        from django.urls import reverse
        from account.models import Account

        staff_user = Account.objects.create_user(
            email='restricted_staff@test.com',
            username='restricted_staff',
            password='StaffPass123',
            first_name='Restricted',
            last_name='Staff'
        )
        staff_user.is_staff = True
        staff_user.is_admin = False
        staff_user.is_superadmin = False
        staff_user.is_active = True
        staff_user.save()

        client.force_login(staff_user)
        url = reverse('admin:store_product_download_import_template')
        response = client.get(url)
        assert response.status_code == 403

    def test_import_and_changelist_views_render_download_link(self, client, admin_user):
        """Test: Las vistas de importación y changelist contienen los enlaces de descarga"""
        from django.urls import reverse

        client.force_login(admin_user)

        # 1. Changelist
        res_change = client.get(reverse('admin:store_product_changelist'))
        assert res_change.status_code == 200
        assert 'download-import-template/' in res_change.content.decode('utf-8')

        # 2. Import products
        res_import = client.get(reverse('admin:import_products'))
        assert res_import.status_code == 200
        content_import = res_import.content.decode('utf-8')
        assert 'download-import-template/' in content_import
        assert 'Plantilla Excel Oficial de Importación' in content_import
        assert 'code' in content_import and 'price' in content_import

        # 3. Update prices
        res_prices = client.get(reverse('admin:update_prices'))
        assert res_prices.status_code == 200
        content_prices = res_prices.content.decode('utf-8')
        assert 'download-import-template/?mode=prices' in content_prices
        assert 'Plantilla Rápida para Precios' in content_prices


@pytest.mark.django_db
class TestBulkChunkedUploadService:
    """Tests unitarios y de integración para la lógica de carga masiva por lotes (chunking)"""

    def create_excel_with_n_rows(self, n: int) -> BytesIO:
        data = [{'code': f'BULK_{i:05d}', 'price': 100.0 + i} for i in range(n)]
        df = pd.DataFrame(data)
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        buf.name = 'bulk_test.xlsx'
        return buf

    def test_start_bulk_upload_session_partitioning_and_cache(self, admin_user):
        """Test: start_bulk_upload_session particiona correctamente en lotes y guarda en caché"""
        from django.core.cache import cache
        buf = self.create_excel_with_n_rows(600)

        # En modo 'prices', chunk_size=500 -> 600 filas deben ser 2 chunks (500 + 100)
        res = ProductService.start_bulk_upload_session(buf, mode='prices', user_id=admin_user.id)

        assert res['success'] is True
        upload_id = res['upload_id']
        assert res['total_rows'] == 600
        assert res['total_chunks'] == 2
        assert res['chunk_size'] == 500

        # Verificar presencia en caché
        meta_key = f"store:bulk:{upload_id}:meta"
        meta = cache.get(meta_key)
        assert meta is not None
        assert meta['user_id'] == admin_user.id
        assert meta['total_rows'] == 600

        assert cache.get(f"store:bulk:{upload_id}:chunk:0") is not None
        assert cache.get(f"store:bulk:{upload_id}:chunk:1") is not None

    def test_process_price_chunks_bulk_update_and_discount_calc(self, admin_user):
        """Test: Procesa lotes de precios con bulk_update y recalcula porcentajes de oferta"""
        # Crear categoría y productos en BD
        cat = Category.objects.create(category_name='Ferretería', slug='ferreteria')
        p1 = Product.objects.create(code='PRICE01', name='Bulón 1', price=100.0, stock=10, category=cat)
        p2 = Product.objects.create(
            code='PRICE02', name='Bulón 2', price=200.0, stock=5, category=cat,
            is_on_sale=True, sale_price=100.0
        )

        excel_data = [
            {'code': 'PRICE01', 'price': '150.00'},
            {'code': 'PRICE02', 'price': '250.00'},
            {'code': 'PRICE_MISSING', 'price': '99.00'},
        ]
        df = pd.DataFrame(excel_data)
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        buf.name = 'prices.xlsx'

        start_res = ProductService.start_bulk_upload_session(buf, mode='prices', user_id=admin_user.id)
        upload_id = start_res['upload_id']

        # Procesar lote 0
        chunk_res = ProductService.process_bulk_upload_chunk(upload_id, chunk_index=0, user_id=admin_user.id)

        assert chunk_res['success'] is True
        assert chunk_res['processed_rows'] == 3
        assert chunk_res['updated'] == 2
        assert chunk_res['errors'] == 1
        assert chunk_res['percent'] == 100
        assert chunk_res['is_done'] is True

        p1.refresh_from_db()
        assert p1.price == 150.00

        p2.refresh_from_db()
        assert p2.price == 250.00
        # Descuento: (250 - 100) / 250 = 60%
        assert p2.discount_percentage == 60

    def test_process_import_chunks_full_catalog(self, admin_user):
        """Test: Procesa lote de importación completa con creación de categorías, tags e IVA"""
        excel_data = [
            {
                'code': 'IMP001',
                'name': 'Tornillo Autoperforante Hexagonal',
                'price': '350.50',
                'category': 'Fijaciones Industriales',
                'subcategories': 'Autoperforantes, Hexagonales',
                'tags': 'Chapa, Zincado',
                'tax_rate': '10.50',
                'stock': '500'
            }
        ]
        df = pd.DataFrame(excel_data)
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        buf.name = 'import.xlsx'

        start_res = ProductService.start_bulk_upload_session(buf, mode='import', user_id=admin_user.id)
        upload_id = start_res['upload_id']

        chunk_res = ProductService.process_bulk_upload_chunk(upload_id, chunk_index=0, user_id=admin_user.id)

        assert chunk_res['success'] is True
        assert chunk_res['created'] == 1
        assert chunk_res['is_done'] is True

        prod = Product.objects.get(code='IMP001')
        assert prod.price == 350.50
        assert prod.tax_rate == Decimal('10.50')
        assert prod.category.category_name == 'Fijaciones Industriales'
        assert prod.subcategories.count() == 2
        assert prod.tags.count() == 2

    def test_chunk_idempotency_on_retry(self, admin_user):
        """Test: Si se reintenta un lote ya procesado por fallo de red, responde idempotentemente"""
        cat = Category.objects.create(category_name='General', slug='general')
        Product.objects.create(code='IDEMP01', name='P1', price=10.0, stock=5, category=cat)

        excel_data = [{'code': 'IDEMP01', 'price': '20.00'}]
        df = pd.DataFrame(excel_data)
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        buf.name = 'idem.xlsx'

        start_res = ProductService.start_bulk_upload_session(buf, mode='prices', user_id=admin_user.id)
        upload_id = start_res['upload_id']

        res1 = ProductService.process_bulk_upload_chunk(upload_id, chunk_index=0, user_id=admin_user.id)
        assert res1['updated'] == 1

        # Segundo intento idéntico
        res2 = ProductService.process_bulk_upload_chunk(upload_id, chunk_index=0, user_id=admin_user.id)
        assert res2['success'] is True
        assert res2['updated'] == 1
        assert res2['processed_rows'] == 1  # No se duplicó a 2

    def test_cancel_bulk_upload_session(self, admin_user):
        """Test: Cancelar sesión elimina los chunks y metadata de la caché"""
        from django.core.cache import cache
        buf = self.create_excel_with_n_rows(10)
        start_res = ProductService.start_bulk_upload_session(buf, mode='prices', user_id=admin_user.id)
        upload_id = start_res['upload_id']

        meta_key = f"store:bulk:{upload_id}:meta"
        assert cache.get(meta_key) is not None

        cancelled = ProductService.cancel_bulk_upload_session(upload_id, user_id=admin_user.id)
        assert cancelled is True
        assert cache.get(meta_key) is None
        assert cache.get(f"store:bulk:{upload_id}:chunk:0") is None

    def test_start_bulk_upload_empty_file_rejected(self, admin_user):
        """Test: Archivo vacío o sin filas es rechazado con error claro"""
        df = pd.DataFrame([])
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        buf.name = 'empty.xlsx'

        res = ProductService.start_bulk_upload_session(buf, mode='prices', user_id=admin_user.id)
        assert res['success'] is False
        assert 'vacío' in res['error'].lower()


@pytest.mark.django_db
class TestAdminBulkChunkedUploadViews:
    """Tests de integración para los endpoints HTTP administrativos de carga por lotes"""

    def test_admin_bulk_upload_start_chunk_end_to_end(self, client, admin_user):
        """Test: Ciclo completo HTTP (start -> chunk -> done) en Django Admin"""
        import json
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(admin_user)

        cat = Category.objects.create(category_name='Tornillería', slug='tornilleria')
        Product.objects.create(code='E2E_01', name='Bulón E2E', price=100.0, stock=5, category=cat)

        excel_data = [{'code': 'E2E_01', 'price': '199.99'}]
        df = pd.DataFrame(excel_data)
        buf = BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        uploaded_file = SimpleUploadedFile(
            'prices_e2e.xlsx',
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # 1. Start session
        start_url = reverse('admin:store_product_bulk_upload_start')
        resp_start = client.post(start_url, {'file': uploaded_file, 'mode': 'prices'})
        assert resp_start.status_code == 200
        data_start = resp_start.json()
        assert data_start['success'] is True
        upload_id = data_start['upload_id']
        assert data_start['total_chunks'] == 1

        # 2. Process chunk 0 via JSON POST
        chunk_url = reverse('admin:store_product_bulk_upload_chunk')
        resp_chunk = client.post(
            chunk_url,
            data=json.dumps({'upload_id': upload_id, 'chunk_index': 0}),
            content_type='application/json'
        )
        assert resp_chunk.status_code == 200
        data_chunk = resp_chunk.json()
        assert data_chunk['success'] is True
        assert data_chunk['updated'] == 1
        assert data_chunk['percent'] == 100
        assert data_chunk['is_done'] is True

        prod = Product.objects.get(code='E2E_01')
        assert prod.price == 199.99

    def test_admin_bulk_upload_anonymous_forbidden_or_redirect(self, client):
        """Test: Usuario anónimo no puede acceder a los endpoints de carga por lotes"""
        from django.urls import reverse
        start_url = reverse('admin:store_product_bulk_upload_start')
        resp = client.post(start_url, {})
        assert resp.status_code == 302
        assert '/admin/login/' in resp.url

    def test_admin_bulk_upload_staff_without_permissions_gets_403(self, client):
        """Test: Usuario staff sin permisos sobre Product recibe 403 Forbidden"""
        from django.urls import reverse
        from account.models import Account

        staff = Account.objects.create_user(
            email='staff_unauthorized@test.com',
            username='staff_unauth',
            password='Password123',
            first_name='Unauth',
            last_name='Staff'
        )
        staff.is_staff = True
        staff.is_active = True
        staff.save()

        client.force_login(staff)

        start_url = reverse('admin:store_product_bulk_upload_start')
        resp = client.post(start_url, {})
        assert resp.status_code == 403

        chunk_url = reverse('admin:store_product_bulk_upload_chunk')
        resp_chunk = client.post(chunk_url, {})
        assert resp_chunk.status_code == 403

    def test_admin_bulk_upload_anti_idor_other_user_blocked(self, client, admin_user):
        """Test: Anti-IDOR: un usuario no puede manipular la sesión de carga iniciada por otro usuario"""
        import json
        from django.urls import reverse
        from django.core.cache import cache
        from account.models import Account

        # Usuario B (otro admin)
        admin_b = Account.objects.create_superuser(
            email='admin_b@test.com',
            username='admin_b',
            password='AdminPass123',
            first_name='Admin',
            last_name='B'
        )

        # Sesión creada por admin_user
        upload_id = 'test_idor_session_123'
        meta = {
            'upload_id': upload_id,
            'mode': 'prices',
            'user_id': admin_user.id,
            'total_rows': 1,
            'total_chunks': 1,
            'chunk_size': 500,
            'processed_rows': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'image_warnings': 0,
            'completed_chunks': [],
            'error_details': [],
            'tags_created': [],
            'created_at': '2026-11-05T00:00:00Z',
            'is_done': False,
        }
        cache.set(f"store:bulk:{upload_id}:meta", meta, timeout=600)

        # Admin B intenta procesar el chunk de admin_user
        client.force_login(admin_b)
        chunk_url = reverse('admin:store_product_bulk_upload_chunk')
        resp = client.post(
            chunk_url,
            data=json.dumps({'upload_id': upload_id, 'chunk_index': 0}),
            content_type='application/json'
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data['permission_denied'] is True

    def test_bulk_upload_start_without_file_returns_400_json(self, client, admin_user):
        """Test: Endpoint start responde 400 con JSON claro si no se adjunta archivo"""
        from django.urls import reverse

        client.force_login(admin_user)
        start_url = reverse('admin:store_product_bulk_upload_start')
        resp = client.post(start_url, {'mode': 'import'})

        assert resp.status_code == 400
        data = resp.json()
        assert data['success'] is False
        assert 'requerido' in data['error'].lower()

    def test_import_and_prices_views_render_local_assets_only(self, client, admin_user):
        """Test: Vistas administrativas renderizan activos locales y no CDNs bloqueados por CSP"""
        from django.urls import reverse

        client.force_login(admin_user)
        for url_name in ('admin:import_products', 'admin:update_prices'):
            resp = client.get(reverse(url_name))
            assert resp.status_code == 200
            content = resp.content.decode('utf-8')
            assert 'js/vendor/lucide.min.js' in content
            assert 'unpkg.com' not in content
            assert 'cdn.tailwindcss.com' not in content

    def test_import_and_prices_views_build_formdata_explicitly(self, client, admin_user):
        """Test: Script en plantillas construye FormData explícitamente evitando omisión por input disabled"""
        from django.urls import reverse

        client.force_login(admin_user)
        for url_name in ('admin:import_products', 'admin:update_prices'):
            resp = client.get(reverse(url_name))
            assert resp.status_code == 200
            content = resp.content.decode('utf-8')
            assert "formData.append('file', file" in content


@pytest.mark.django_db
class TestProductExport:
    """Tests unitarios y de integración para la exportación masiva de productos a Excel."""

    def test_export_products_workbook_structure_matches_import_template(self):
        """Test: El Excel exportado conserva exactamente las 3 hojas y 33 columnas de la plantilla oficial."""
        import openpyxl
        from openpyxl.utils import get_column_letter

        cat = Category.objects.create(category_name='Bulonería', slug='buloneria')
        Product.objects.create(
            code='00100100025',
            name='Bulón Hexagonal G2',
            price=1250.50,
            stock=100,
            category=cat,
        )

        buffer = ProductService.export_products_workbook()
        wb = openpyxl.load_workbook(buffer, data_only=False)

        assert wb.sheetnames == ['Productos', 'Guía y Ejemplos', 'Guía de Imágenes']

        ws1 = wb['Productos']
        header_row = [cell.value for cell in ws1[1]]
        expected_columns = [col['name'] for col in ProductService.IMPORT_TEMPLATE_COLUMNS]
        assert len(header_row) == 33
        assert header_row == expected_columns
        assert ws1.freeze_panes == 'A2'
        assert ws1.max_row == 2

        for col_name in ['code', 'diameter', 'length', 'diameter_relation', 'gtin', 'mpn']:
            col_idx = header_row.index(col_name) + 1
            col_letter = get_column_letter(col_idx)
            assert ws1.column_dimensions[col_letter].number_format == '@'

        assert wb['Guía y Ejemplos'].max_row > 10
        assert wb['Guía de Imágenes'].max_row > 5

    def test_export_and_reimport_full_roundtrip(self):
        """Test round-trip: Exportar catálogo, editar valores y re-importar preserva todos los datos."""
        import openpyxl
        from store.models import ProductTag

        cat = Category.objects.create(category_name='Bulonería', slug='buloneria')
        sub1 = SubCategory.objects.create(subcategory_name='Hexagonales', slug='hexagonales', category=cat)
        sub2 = SubCategory.objects.create(subcategory_name='Grado 2', slug='grado-2', category=cat)
        tag1 = ProductTag.objects.create(name='Zincado', slug='zincado')
        tag2 = ProductTag.objects.create(name='Industrial', slug='industrial')

        p1 = Product.objects.create(
            code='00100100025',
            name='Bulón Hexagonal G2',
            diameter='1/4"',
            length='1-1/2"',
            description='Bulón estándar zincado.',
            price=1250.50,
            stock=500,
            category=cat,
            tax_rate=Decimal('10.50'),
            brand='Bulonera Alvear',
            condition='new',
            norm='SAE J429',
            grade='Grado 2',
            material='Acero al carbono',
            gtin='7791234567890',
            mpn='BH-G2-14112',
            meta_title='Bulón Hexagonal G2 | Bulonera Alvear',
            meta_description='Stock en Resistencia, Chaco.',
            meta_keywords='bulon, hexagonal',
        )
        p1.subcategories.add(sub1, sub2)
        p1.tags.add(tag1, tag2)

        p2 = Product.objects.create(
            code='MAQ-TAL-001',
            name='Taladro Percutor 18V',
            price=185000.00,
            stock=15,
            category=cat,
        )
        p2.subcategories.add(sub1)

        # Exportar a Excel
        export_buffer = ProductService.export_products_workbook()
        wb = openpyxl.load_workbook(export_buffer)
        ws = wb['Productos']
        headers = [c.value for c in ws[1]]
        code_idx = headers.index('code') + 1
        price_idx = headers.index('price') + 1
        stock_idx = headers.index('stock') + 1

        # Verificar preservación de ceros iniciales y medidas fraccionarias
        assert ws.cell(row=2, column=code_idx).value == '00100100025'
        assert ws.cell(row=2, column=headers.index('diameter') + 1).value == '1/4"'
        assert ws.cell(row=2, column=headers.index('length') + 1).value == '1-1/2"'
        assert ws.cell(row=2, column=headers.index('tax_rate') + 1).value == '10.50'

        # Editar precio y stock en el Excel exportado antes de re-importar
        ws.cell(row=2, column=price_idx).value = 1400.75
        ws.cell(row=2, column=stock_idx).value = 420

        reupload_buf = BytesIO()
        wb.save(reupload_buf)
        reupload_buf.seek(0)
        reupload_buf.name = 'catalogo_reimport.xlsx'

        result = ProductService.import_from_file(reupload_buf)
        assert result.errors == 0
        assert result.updated == 2

        p1.refresh_from_db()
        assert p1.code == '00100100025'
        assert p1.price == 1400.75
        assert p1.stock == 420
        assert p1.diameter == '1/4"'
        assert p1.length == '1-1/2"'
        assert p1.tax_rate == Decimal('10.50')
        assert p1.subcategories.count() == 2
        assert p1.tags.count() == 2

    def test_export_products_filters_by_category_subcategory_and_availability(self):
        """Test: Los filtros de categoría, subcategoría y disponibilidad exportan el subconjunto exacto sin duplicar."""
        import openpyxl

        cat1 = Category.objects.create(category_name='Bulonería', slug='buloneria')
        cat2 = Category.objects.create(category_name='Herramientas', slug='herramientas')
        sub1 = SubCategory.objects.create(subcategory_name='Tuercas', slug='tuercas', category=cat1)
        sub2 = SubCategory.objects.create(subcategory_name='Arandelas', slug='arandelas', category=cat1)
        sub3 = SubCategory.objects.create(subcategory_name='Eléctricas', slug='electricas', category=cat2)

        p1 = Product.objects.create(code='F001', name='Tuerca M8', price=10.0, stock=5, category=cat1, is_available=True)
        p1.subcategories.add(sub1, sub2)
        p2 = Product.objects.create(code='F002', name='Arandela M8 Inactivo', price=5.0, stock=0, category=cat1, is_available=False)
        p2.subcategories.add(sub2)
        p3 = Product.objects.create(code='F003', name='Amoladora', price=500.0, stock=2, category=cat2, is_available=True)
        p3.subcategories.add(sub3)

        def read_codes(buf):
            wb = openpyxl.load_workbook(buf)
            ws = wb['Productos']
            return [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]

        assert read_codes(ProductService.export_products_workbook(category_id=cat1.id)) == ['F001', 'F002']
        assert read_codes(ProductService.export_products_workbook(category_id=cat1.id, only_available=True)) == ['F001']
        assert read_codes(ProductService.export_products_workbook(subcategory_id=sub2.id)) == ['F001', 'F002']
        assert read_codes(ProductService.export_products_workbook(subcategory_id=sub2.id, only_available=True)) == ['F001']
        assert read_codes(ProductService.export_products_workbook(only_available=True)) == ['F001', 'F003']

    def test_export_products_sanitizes_control_chars_and_formula_strings(self):
        """Test: Caracteres XML ilegales y textos que inician con '=' no rompen ni generan fórmulas en Excel."""
        import openpyxl

        cat = Category.objects.create(category_name='General', slug='general')
        Product.objects.create(
            code='=BAD01',
            name='Producto Especial',
            description='=== OFERTA ESPECIAL ===\x0bTexto con control',
            price=99.0,
            stock=10,
            category=cat,
        )

        buf = ProductService.export_products_workbook()
        wb = openpyxl.load_workbook(buf, data_only=False)
        ws = wb['Productos']
        headers = [c.value for c in ws[1]]

        code_cell = ws.cell(row=2, column=headers.index('code') + 1)
        desc_cell = ws.cell(row=2, column=headers.index('description') + 1)

        assert code_cell.value == '=BAD01'
        assert code_cell.data_type == 's'
        assert desc_cell.value == '=== OFERTA ESPECIAL ===Texto con control'
        assert desc_cell.data_type == 's'

    def test_export_products_constant_query_count_anti_n_plus_1(self, django_assert_num_queries):
        """Test: La exportación ejecuta un número constante de queries SQL sin importar la cantidad de productos."""
        from store.models import ProductTag

        cat = Category.objects.create(category_name='Bulonería', slug='buloneria')
        sub = SubCategory.objects.create(subcategory_name='Hexagonales', slug='hexagonales', category=cat)
        tag = ProductTag.objects.create(name='Zincado', slug='zincado')

        for i in range(15):
            prod = Product.objects.create(
                code=f'N1_{i:04d}',
                name=f'Bulón Test {i}',
                price=100.0 + i,
                stock=10,
                category=cat,
            )
            prod.subcategories.add(sub)
            prod.tags.add(tag)

        # 6 queries planas: subcats + related_subcats + tags + gallery + faqs + products iterator
        with django_assert_num_queries(6):
            buf = ProductService.export_products_workbook()
        buf.close()

    def test_admin_export_endpoints_and_action(self, client, admin_user):
        """Test: Permisos, página de filtros, descarga filtrada y acción de seleccionados en Django Admin."""
        import openpyxl
        from django.urls import reverse
        from account.models import Account

        cat1 = Category.objects.create(category_name='Bulonería', slug='buloneria')
        cat2 = Category.objects.create(category_name='Herramientas', slug='herramientas')
        sub1 = SubCategory.objects.create(subcategory_name='Hexagonales', slug='hexagonales', category=cat1)

        p1 = Product.objects.create(code='ADM001', name='Bulón Admin 1', price=50.0, stock=10, category=cat1, is_available=True)
        p1.subcategories.add(sub1)
        p2 = Product.objects.create(code='ADM002', name='Taladro Admin 2', price=500.0, stock=3, category=cat2, is_available=True)

        export_page_url = reverse('admin:store_product_export')
        download_url = reverse('admin:store_product_export_download')

        # 1. Anónimo redirigido al login
        resp_anon = client.get(export_page_url)
        assert resp_anon.status_code == 302
        assert '/admin/login/' in resp_anon.url

        # 2. Staff sin permisos recibe 403
        staff = Account.objects.create_user(
            email='staff_no_export@test.com',
            username='staff_no_export',
            password='Password123',
            first_name='No',
            last_name='Perm',
        )
        staff.is_staff = True
        staff.is_active = True
        staff.save()
        client.force_login(staff)

        assert client.get(export_page_url).status_code == 403
        assert client.get(download_url).status_code == 403

        # 3. Admin autenticado accede a vista de exportación y botones en changelist
        client.force_login(admin_user)
        changelist_resp = client.get(reverse('admin:store_product_changelist'))
        assert changelist_resp.status_code == 200
        assert 'export-products/' in changelist_resp.content.decode('utf-8')

        page_resp = client.get(export_page_url)
        assert page_resp.status_code == 200
        page_html = page_resp.content.decode('utf-8')
        assert 'Bulonería' in page_html
        assert 'Hexagonales' in page_html
        assert 'unpkg.com' not in page_html

        # 4. Descarga filtrada por categoría
        dl_resp = client.get(f"{download_url}?category_id={cat1.id}")
        assert dl_resp.status_code == 200
        assert dl_resp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'productos_bulonera_buloneria_' in dl_resp['Content-Disposition']

        wb = openpyxl.load_workbook(BytesIO(b''.join(dl_resp.streaming_content)))
        ws = wb['Productos']
        assert ws.max_row == 2
        assert ws.cell(row=2, column=1).value == 'ADM001'

        # 4b. Descarga filtrada por subcategoría
        dl_sub_resp = client.get(f"{download_url}?subcategory_id={sub1.id}&only_available=1")
        assert dl_sub_resp.status_code == 200
        assert 'productos_bulonera_hexagonales_' in dl_sub_resp['Content-Disposition']
        wb_sub = openpyxl.load_workbook(BytesIO(b''.join(dl_sub_resp.streaming_content)))
        ws_sub = wb_sub['Productos']
        assert ws_sub.max_row == 2
        assert ws_sub.cell(row=2, column=1).value == 'ADM001'

        # 5. Acción sobre productos seleccionados en changelist
        action_resp = client.post(
            reverse('admin:store_product_changelist'),
            {'action': 'export_selected_products_excel', '_selected_action': [str(p2.id)]},
        )
        assert action_resp.status_code == 200
        assert action_resp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        wb_sel = openpyxl.load_workbook(BytesIO(b''.join(action_resp.streaming_content)))
        ws_sel = wb_sel['Productos']
        assert ws_sel.max_row == 2
        assert ws_sel.cell(row=2, column=1).value == 'ADM002'

    def test_related_subcategories_roundtrip_preserve_clear_and_alias(self):
        """Test: Round-trip de las 3 columnas de relación, alias ProductRelation, preservar con vacío y limpiar con '-'."""
        import openpyxl

        cat = Category.objects.create(category_name='Bulonería', slug='buloneria')
        sub_bulon = SubCategory.objects.create(subcategory_name='bulon milimetrico', slug='bulon-milimetrico', category=cat)
        sub_tuerca = SubCategory.objects.create(subcategory_name='Tuercas Hexagonales', slug='tuercas-hexagonales', category=cat)
        sub_arandela = SubCategory.objects.create(subcategory_name='Arandelas', slug='arandelas', category=cat)

        prod = Product.objects.create(
            code='REL-001',
            name='Bulón M6 x 100',
            diameter='6 x P 1.0',
            length='100',
            thread_formats='MA (rosca gruesa)',
            price=100.0,
            stock=50,
            category=cat,
            diameter_relation='6 x P 1.0',
            thread_formats_relation='MA (rosca gruesa)',
        )
        prod.subcategories.add(sub_bulon)
        prod.related_subcategories.add(sub_tuerca, sub_arandela)

        # 1. Exportar y verificar presencia de las 3 columnas
        export_buf = ProductService.export_products_workbook()
        wb = openpyxl.load_workbook(export_buf)
        ws = wb['Productos']
        headers = [c.value for c in ws[1]]
        assert ws.cell(row=2, column=headers.index('related_subcategories') + 1).value in (
            'Tuercas Hexagonales, Arandelas',
            'Arandelas, Tuercas Hexagonales',
        )
        assert ws.cell(row=2, column=headers.index('diameter_relation') + 1).value == '6 x P 1.0'
        assert ws.cell(row=2, column=headers.index('thread_formats_relation') + 1).value == 'MA (rosca gruesa)'

        # 2. Importar con alias ProductRelation + subcategoría inexistente (NO debe crear fantasma)
        alias_data = [{
            'code': 'REL-002',
            'name': 'Tirafondo 6 x 50',
            'price': '80.00',
            'category': 'Bulonería',
            'ProductRelation': 'Arandelas, Subcat Fantasma Inexistente',
            'diameter_relation': '8, 10',
        }]
        res_alias = ProductService.import_from_file(TestProductImport().create_test_excel(alias_data))
        assert res_alias.errors == 0
        assert res_alias.created == 1
        assert not SubCategory.objects.filter(subcategory_name='Subcat Fantasma Inexistente').exists()
        prod2 = Product.objects.get(code='REL-002')
        assert list(prod2.related_subcategories.values_list('subcategory_name', flat=True)) == ['Arandelas']
        assert prod2.diameter_relation == '8, 10'

        # 3. Celda vacía o Excel legacy de 30 cols preserva relaciones existentes
        preserve_data = [{
            'code': 'REL-001',
            'price': '120.00',
            'related_subcategories': '',
            'diameter_relation': '',
            'thread_formats_relation': '',
        }]
        res_preserve = ProductService.import_from_file(TestProductImport().create_test_excel(preserve_data))
        assert res_preserve.errors == 0
        prod.refresh_from_db()
        assert prod.related_subcategories.count() == 2
        assert prod.diameter_relation == '6 x P 1.0'

        # 4. Valor '-' limpia explícitamente relaciones y criterios
        clear_data = [{
            'code': 'REL-001',
            'price': '120.00',
            'related_subcategories': '-',
            'diameter_relation': '-',
            'thread_formats_relation': '-',
        }]
        res_clear = ProductService.import_from_file(TestProductImport().create_test_excel(clear_data))
        assert res_clear.errors == 0
        prod.refresh_from_db()
        assert prod.related_subcategories.count() == 0
        assert prod.diameter_relation == ''
        assert prod.thread_formats_relation == ''

    def test_bulk_upload_imports_relation_columns(self, admin_user):
        """Test: Carga masiva por lotes (chunking) persiste las 3 columnas de relación."""
        cat = Category.objects.create(category_name='Bulonería', slug='buloneria')
        SubCategory.objects.create(subcategory_name='Arandelas', slug='arandelas', category=cat)

        excel_data = [{
            'code': 'BULK-REL-01',
            'name': 'Bulón Bulk 1/4',
            'price': '500.00',
            'stock': '20',
            'category': 'Bulonería',
            'related_subcategories': 'Arandelas',
            'diameter_relation': '1/4',
            'thread_formats_relation': 'UNC',
        }]
        buf = TestProductImport().create_test_excel(excel_data)
        start_res = ProductService.start_bulk_upload_session(buf, mode='import', user_id=admin_user.id)
        assert start_res['success'] is True
        chunk_res = ProductService.process_bulk_upload_chunk(
            start_res['upload_id'], chunk_index=0, user_id=admin_user.id
        )
        assert chunk_res['success'] is True
        assert chunk_res['created'] == 1

        prod = Product.objects.get(code='BULK-REL-01')
        assert list(prod.related_subcategories.values_list('subcategory_name', flat=True)) == ['Arandelas']
        assert prod.diameter_relation == '1/4'
        assert prod.thread_formats_relation == 'UNC'

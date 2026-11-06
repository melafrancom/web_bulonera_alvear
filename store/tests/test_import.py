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
        """Test: Genera la plantilla completa con 30 columnas canónicas y 3 hojas bien formateadas"""
        import openpyxl
        from openpyxl.utils import get_column_letter

        buffer = ProductService.generate_import_template_workbook(mode='full')
        
        # Validar que es un archivo Excel válido
        wb = openpyxl.load_workbook(buffer, data_only=False)
        assert wb.sheetnames == ['Productos', 'Guía y Ejemplos', 'Guía de Imágenes']
        
        ws1 = wb['Productos']
        # Fila 1 debe tener exactamente las 30 columnas canónicas
        header_row = [cell.value for cell in ws1[1]]
        expected_columns = [col['name'] for col in ProductService.IMPORT_TEMPLATE_COLUMNS]
        assert len(header_row) == 30
        assert header_row == expected_columns
        assert 'tax_rate' in header_row
        assert 'tags' in header_row
        assert 'code' in header_row
        assert 'price' in header_row

        # Hoja 1 NO debe tener filas de datos pre-cargadas para evitar crear registros basura
        assert ws1.max_row == 1

        # Paneles inmovilizados
        assert ws1.freeze_panes == 'A2'

        # Formato texto '@' en columnas sensibles
        for col_name in ['code', 'diameter', 'length', 'gtin', 'mpn']:
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

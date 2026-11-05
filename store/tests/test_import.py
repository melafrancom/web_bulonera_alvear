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
        """Test: Actualización de precios solo modifica el precio"""
        category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        product = Product.objects.create(
            code='TEST001',
            name='Producto Test',
            price=100.00,
            stock=10,
            category=category
        )
        
        data = [{
            'code': 'TEST001',
            'price': 150.00
        }]
        
        excel_file = self.create_test_excel(data)
        result = ProductService.update_prices_from_file(excel_file)
        
        assert result.updated == 1
        assert result.errors == 0
        
        product.refresh_from_db()
        assert product.price == 150.00
        assert product.name == 'Producto Test'  # No cambió
        assert product.stock == 10  # No cambió
    
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

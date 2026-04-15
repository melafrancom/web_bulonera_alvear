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

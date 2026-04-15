"""Tests for Cart Services"""
import pytest
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware

from cart.models import Cart, CartItem
from cart.services import CartService
from store.models import Product
from category.models import Category

Account = get_user_model()


@pytest.mark.django_db
class TestCartService(TestCase):
    """Tests para CartService"""
    
    def setUp(self):
        """Setup para tests del servicio"""
        self.factory = RequestFactory()
        
        # Crear categoría y producto
        self.category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=100.00,
            stock=10,
            category=self.category
        )
        
        # Crear usuario
        self.user = Account.objects.create_user(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )
    
    def _create_request_with_session(self):
        """Helper para crear request con sesión"""
        request = self.factory.get('/')
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        return request
    
    def test_get_or_create_cart_id(self):
        """Test: Obtener o crear cart_id"""
        request = self._create_request_with_session()
        
        cart_id = CartService.get_or_create_cart_id(request)
        
        self.assertIsNotNone(cart_id)
        self.assertEqual(cart_id, request.session.session_key)
    
    def test_add_to_cart_authenticated_user(self):
        """Test: Agregar producto al carrito (usuario autenticado)"""
        request = self._create_request_with_session()
        
        cart_item = CartService.add_to_cart(
            request=request,
            product=self.product,
            quantity=2,
            user=self.user
        )
        
        self.assertEqual(cart_item.user, self.user)
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.purchase_price, self.product.price)
    
    def test_add_to_cart_anonymous_user(self):
        """Test: Agregar producto al carrito (usuario anónimo)"""
        request = self._create_request_with_session()
        
        cart_item = CartService.add_to_cart(
            request=request,
            product=self.product,
            quantity=1
        )
        
        self.assertIsNotNone(cart_item.cart)
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 1)
    
    def test_add_to_cart_increment_existing(self):
        """Test: Agregar producto existente incrementa cantidad"""
        request = self._create_request_with_session()
        
        # Primera adición
        CartService.add_to_cart(
            request=request,
            product=self.product,
            quantity=1,
            user=self.user
        )
        
        # Segunda adición del mismo producto
        cart_item = CartService.add_to_cart(
            request=request,
            product=self.product,
            quantity=2,
            user=self.user
        )
        
        self.assertEqual(cart_item.quantity, 3)  # 1 + 2
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 1)
    
    def test_add_to_cart_invalid_quantity(self):
        """Test: Cantidad inválida genera error"""
        request = self._create_request_with_session()
        
        with self.assertRaises(ValueError):
            CartService.add_to_cart(
                request=request,
                product=self.product,
                quantity=0,
                user=self.user
            )
    
    def test_get_cart_items_authenticated(self):
        """Test: Obtener items del carrito (usuario autenticado)"""
        request = self._create_request_with_session()
        
        # Crear items
        CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2,
            purchase_price=100.00
        )
        
        cart_items = CartService.get_cart_items(request, self.user)
        
        self.assertEqual(cart_items.count(), 1)
        self.assertEqual(cart_items.first().quantity, 2)
    
    def test_get_cart_items_anonymous(self):
        """Test: Obtener items del carrito (usuario anónimo)"""
        request = self._create_request_with_session()
        cart_id = CartService.get_or_create_cart_id(request)
        cart = Cart.objects.create(cart_id=cart_id)
        
        # Crear item
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
            purchase_price=100.00
        )
        
        cart_items = CartService.get_cart_items(request)
        
        self.assertEqual(cart_items.count(), 1)
    
    def test_calculate_cart_totals(self):
        """Test: Calcular totales del carrito"""
        # Crear items
        item1 = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2,
            purchase_price=100.00
        )
        
        cart_items = CartItem.objects.filter(user=self.user)
        totals = CartService.calculate_cart_totals(cart_items)
        
        self.assertEqual(totals['total'], Decimal('200.00'))
        self.assertEqual(totals['quantity'], 2)
    
    def test_remove_from_cart_decrement(self):
        """Test: Remover item decrementa cantidad"""
        request = self._create_request_with_session()
        
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=3,
            purchase_price=100.00
        )
        
        success = CartService.remove_from_cart(
            request=request,
            product_id=self.product.id,
            cart_item_id=cart_item.id,
            user=self.user,
            remove_completely=False
        )
        
        self.assertTrue(success)
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)
    
    def test_remove_from_cart_delete(self):
        """Test: Remover item con cantidad 1 lo elimina"""
        request = self._create_request_with_session()
        
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1,
            purchase_price=100.00
        )
        
        success = CartService.remove_from_cart(
            request=request,
            product_id=self.product.id,
            cart_item_id=cart_item.id,
            user=self.user,
            remove_completely=False
        )
        
        self.assertTrue(success)
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())
    
    def test_remove_from_cart_completely(self):
        """Test: Remover item completamente"""
        request = self._create_request_with_session()
        
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=5,
            purchase_price=100.00
        )
        
        success = CartService.remove_from_cart(
            request=request,
            product_id=self.product.id,
            cart_item_id=cart_item.id,
            user=self.user,
            remove_completely=True
        )
        
        self.assertTrue(success)
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())
    
    def test_get_cart_count(self):
        """Test: Obtener conteo de items"""
        request = self._create_request_with_session()
        
        CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=3,
            purchase_price=100.00
        )
        
        count = CartService.get_cart_count(request, self.user)
        
        self.assertEqual(count, 3)
    
    def test_clear_cart(self):
        """Test: Limpiar carrito"""
        request = self._create_request_with_session()
        
        CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2,
            purchase_price=100.00
        )
        
        CartService.clear_cart(request, self.user)
        
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 0)
    
    def test_merge_cart_on_login(self):
        """Test: Fusionar carrito anónimo al hacer login"""
        request = self._create_request_with_session()
        cart_id = CartService.get_or_create_cart_id(request)
        cart = Cart.objects.create(cart_id=cart_id)
        
        # Crear item anónimo
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2,
            purchase_price=100.00
        )
        
        # Fusionar al hacer login
        CartService.merge_cart_on_login(request, self.user)
        
        # Verificar que el item ahora pertenece al usuario
        user_items = CartItem.objects.filter(user=self.user)
        self.assertEqual(user_items.count(), 1)
        self.assertEqual(user_items.first().quantity, 2)

"""Tests for Cart Models"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

from cart.models import Cart, CartItem
from store.models import Product
from category.models import Category

Account = get_user_model()


@pytest.mark.django_db
class TestCartModel(TestCase):
    """Tests para el modelo Cart"""
    
    def test_cart_creation(self):
        """Test: Crear carrito exitosamente"""
        cart = Cart.objects.create(cart_id='test-session-123')
        
        self.assertEqual(cart.cart_id, 'test-session-123')
        self.assertIsNotNone(cart.date_added)
    
    def test_cart_str_representation(self):
        """Test: Representación string de carrito"""
        cart = Cart.objects.create(cart_id='test-session-123')
        self.assertEqual(str(cart), 'test-session-123')


@pytest.mark.django_db
class TestCartItemModel(TestCase):
    """Tests para el modelo CartItem"""
    
    def setUp(self):
        """Setup para tests de CartItem"""
        # Crear categoría
        self.category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        
        # Crear producto
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
        
        # Crear carrito
        self.cart = Cart.objects.create(cart_id='test-session')
    
    def test_cart_item_creation_with_user(self):
        """Test: Crear cart item con usuario autenticado"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )
        
        self.assertEqual(cart_item.user, self.user)
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 2)
        self.assertTrue(cart_item.is_active)
    
    def test_cart_item_creation_with_cart(self):
        """Test: Crear cart item con carrito anónimo"""
        cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1
        )
        
        self.assertEqual(cart_item.cart, self.cart)
        self.assertEqual(cart_item.product, self.product)
    
    def test_cart_item_purchase_price_auto_set(self):
        """Test: Precio de compra se establece automáticamente"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        
        self.assertEqual(cart_item.purchase_price, self.product.price)
    
    def test_cart_item_purchase_price_sale(self):
        """Test: Precio de compra usa precio de oferta si está disponible"""
        self.product.is_on_sale = True
        self.product.sale_price = 80.00
        self.product.save()
        
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        
        self.assertEqual(cart_item.purchase_price, 80.00)
    
    def test_cart_item_sub_total(self):
        """Test: Cálculo de subtotal"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=3,
            purchase_price=100.00
        )
        
        self.assertEqual(cart_item.sub_total, 300.00)

import os
import pytest
import django
from django.conf import settings

# Asegurarse de que Django esté configurado
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.test')
django.setup()

from account.models import Account, UserProfile
from category.models import Category, SubCategory
from store.models import Product, ReviewRating
from cart.models import Cart, CartItem


@pytest.fixture
def db_session(db):
    """Fixture que proporciona acceso a la base de datos para tests."""
    return db


@pytest.fixture
def user(db_session):
    """Crea un usuario de test."""
    user = Account.objects.create_user(
        email='testuser@test.com',
        username='testuser',
        password='TestPass123',
        first_name='Test',
        last_name='User'
    )
    user.phone = '+5491234567890'
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def admin_user(db_session):
    """Crea un usuario administrador de test."""
    user = Account.objects.create_user(
        email='admin@test.com',
        username='admin',
        password='AdminPass123',
        first_name='Admin',
        last_name='User'
    )
    user.is_admin = True
    user.is_active = True
    user.is_staff = True
    user.is_superadmin = True
    user.save()
    return user


@pytest.fixture
def category(db_session):
    """Crea una categoría de test."""
    return Category.objects.create(
        category_name='Tornillos',
        slug='tornillos',
        description='Tornillos variados'
    )


@pytest.fixture
def product(db_session, category):
    """Crea un producto de test."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    mock_image = SimpleUploadedFile("test_image.png", b"file_content", content_type="image/png")
    return Product.objects.create(
        code='SCREW-001',
        name='Tornillo Acero Inox 3mm',
        slug='tornillo-acero-inox-3mm',
        description='Tornillo de acero inoxidable',
        price=10.50,
        stock=100,
        category=category,
        is_available=True,
        diameter='3mm',
        length='20mm',
        images=mock_image
    )


@pytest.fixture
def cart(db_session, user):
    """Crea un carrito de test para un usuario."""
    cart = Cart.objects.create(cart_id=f'cart_{user.id}')
    return cart


@pytest.fixture
def cart_item(db_session, cart, product):
    """Crea un item en el carrito de test."""
    return CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=5,
        is_active=True
    )


@pytest.fixture
def client_with_user(client, user):
    """Cliente HTTP autenticado como usuario de test."""
    client.login(email='testuser@test.com', password='TestPass123')
    return client


@pytest.fixture
def api_client():
    """Cliente API REST para tests."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    """Cliente API autenticado."""
    api_client.force_authenticate(user=user)
    return api_client

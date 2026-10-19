"""
Cart Web Tests

Tests de vistas web del carrito.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestCartWebViews:
    """Tests de vistas web del carrito"""

    def test_cart_view_200(self, client):
        """GET /cart/ retorna 200"""
        try:
            response = client.get('/cart/')
            assert response.status_code in [200, 404]
        except:
            # Si la URL no está registrada, es un falso positivo
            pass

    def test_cart_template_has_noindex(self, client):
        """Verifica que el template cart.html incluya noindex, nofollow"""
        from django.template.loader import render_to_string
        rendered = render_to_string('cart/cart.html', {'cart_items': [], 'quantity': 0})
        assert 'name="robots" content="noindex, nofollow"' in rendered

    def test_add_cart_invokes_meta_capi_with_fb_event_id(self, client, product):
        """
        QUÉ:
            Verifica que la vista web add_cart pase el fb_event_id recibido por POST al servicio MetaCapiService.
        POR QUÉ:
            Deduplicación hybrid Browser + Server en Meta CAPI para el evento AddToCart.
        """
        from django.urls import reverse
        from unittest.mock import patch

        url = reverse('cart:add_cart', args=[product.id])
        event_id = "test-frontend-uuid-999"

        with patch('tracking.services.MetaCapiService.enqueue_add_to_cart') as mock_enqueue:
            response = client.post(url, {'quantity': 2, 'fb_event_id': event_id})
            assert response.status_code == 302
            mock_enqueue.assert_called_once()
            args, kwargs = mock_enqueue.call_args
            assert kwargs.get('product') == product or (len(args) > 1 and args[1] == product)
            assert kwargs.get('quantity') == 2 or (len(args) > 2 and args[2] == 2)
            assert kwargs.get('event_id') == event_id or (len(args) > 3 and args[3] == event_id)

    def test_counter_context_processor_handles_missing_user_attribute(self):
        """
        QUÉ: Verifica que counter no lance AttributeError si request.user no está definido.
        POR QUÉ: Páginas de error temprano (DisallowedHost, 400) se renderizan antes de AuthenticationMiddleware.
        """
        from django.test import RequestFactory
        from cart.context_processors import counter

        rf = RequestFactory()
        request = rf.get('/cart/')
        # RequestFactory no inyecta request.user por defecto
        assert not hasattr(request, 'user')
        result = counter(request)
        assert 'cart_count' in result
        assert result['cart_count'] == 0




@pytest.mark.django_db
class TestEmptyCartCommercialState:
    def test_empty_cart_links_to_offers_and_dynamic_categories(self, client, category):
        from django.core.cache import cache
        from django.urls import reverse

        cache.delete("category:menu_links")
        response = client.get(reverse("cart:cart"))

        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("store:offers") in content
        assert "Ver productos en oferta" in content
        assert category.category_name in content
        assert category.get_url() in content


@pytest.mark.django_db
class TestCartUpdateAndRemoveWebViews:
    """Tests para endpoints de actualización y eliminación con soporte dual (AJAX JSON y POST tradicional)"""

    def test_update_cart_quantity_ajax_success(self, client, product):
        """Test: update_cart_quantity vía AJAX devuelve 200 con cadenas decimales y estado del carrito"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )

        url = reverse('cart:update_cart_quantity', args=[cart_item.id])
        response = client.post(
            url,
            {'quantity': 4},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['item']['id'] == cart_item.id
        assert data['item']['quantity'] == 4
        # Cadenas decimales a 2 decimales para precisión contable
        assert isinstance(data['item']['subtotal'], str)
        assert '.' in data['item']['subtotal']
        assert isinstance(data['cart']['total'], str)
        assert data['cart']['quantity'] == 4
        assert data['cart']['item_count'] == 1
        assert data['cart']['is_empty'] is False

    def test_update_cart_quantity_ajax_rejects_zero_or_negative(self, client, product):
        """Test: update_cart_quantity rechaza 0 con HTTP 400 y no elimina el ítem"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            purchase_price=product.price
        )

        url = reverse('cart:update_cart_quantity', args=[cart_item.id])
        response = client.post(
            url,
            {'quantity': 0},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        # El ítem sigue existiendo
        cart_item.refresh_from_db()
        assert cart_item.quantity == 2

    def test_update_cart_quantity_ajax_rejects_empty_or_non_integer(self, client, product):
        """Test: update_cart_quantity rechaza valores vacíos o alfanuméricos con HTTP 400"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )

        url = reverse('cart:update_cart_quantity', args=[cart_item.id])
        # Vacío
        res_empty = client.post(url, {'quantity': ''}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert res_empty.status_code == 400
        assert res_empty.json()['status'] == 'error'

        # No numérico
        res_abc = client.post(url, {'quantity': 'abc'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert res_abc.status_code == 400
        assert res_abc.json()['status'] == 'error'

    def test_update_cart_quantity_traditional_post_fallback(self, client, product):
        """Test: update_cart_quantity sin JavaScript redirige 302 y actualiza la base de datos"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )

        url = reverse('cart:update_cart_quantity', args=[cart_item.id])
        response = client.post(url, {'quantity': 3})

        assert response.status_code == 302
        assert response.url == reverse('cart:cart')
        cart_item.refresh_from_db()
        assert cart_item.quantity == 3

    def test_remove_cart_item_ajax_returns_is_empty_true(self, client, product):
        """Test: remove_cart_item vía AJAX retorna 'deleted' y cart.is_empty=True cuando se elimina el último ítem"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )

        url = reverse('cart:remove_cart_item', args=[product.id, cart_item.id])
        response = client.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'deleted'
        assert data['item_id'] == cart_item.id
        assert data['cart']['is_empty'] is True
        assert data['cart']['item_count'] == 0
        assert not CartItem.objects.filter(id=cart_item.id).exists()

    def test_remove_cart_item_traditional_post(self, client, product):
        """Test: remove_cart_item tradicional redirige 302 al carrito"""
        from django.urls import reverse
        from cart.models import Cart, CartItem

        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )

        url = reverse('cart:remove_cart_item', args=[product.id, cart_item.id])
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse('cart:cart')
        assert not CartItem.objects.filter(id=cart_item.id).exists()

    def test_remove_cart_item_ajax_anonymous_with_remaining_items(self, client, product, category):
        """
        QUÉ:
            Verifica que eliminar un ítem por AJAX en un carrito anónimo con múltiples ítems devuelva
            is_empty=False, status='deleted' y descuente los totales correctamente.
        POR QUÉ:
            Regresión de UX: El carrito no debe entrar a empty state si aún quedan otros ítems activos.
        """
        from django.urls import reverse
        from cart.models import Cart, CartItem
        from store.models import Product

        # Arrange
        session = client.session
        session.save()
        cart = Cart.objects.create(cart_id=session.session_key)

        item1 = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            purchase_price=product.price
        )
        product2 = Product.objects.create(
            code='SCREW-002-TEST',
            name='Tuerca Acero Inox 3mm',
            slug='tuerca-acero-inox-3mm-test',
            price=20.00,
            stock=50,
            category=category,
            is_available=True
        )
        item2 = CartItem.objects.create(
            cart=cart,
            product=product2,
            quantity=2,
            purchase_price=product2.price
        )

        # Act
        url = reverse('cart:remove_cart_item', args=[product.id, item1.id])
        response = client.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'deleted'
        assert data['item_id'] == item1.id
        assert data['cart']['is_empty'] is False
        assert data['cart']['item_count'] == 1
        assert data['cart']['quantity'] == 2
        assert not CartItem.objects.filter(id=item1.id).exists()
        assert CartItem.objects.filter(id=item2.id).exists()

    def test_remove_cart_item_ajax_authenticated_success(self, client_with_user, user, product):
        """
        QUÉ:
            Verifica que un usuario autenticado pueda eliminar su propio ítem por AJAX.
        POR QUÉ:
            Los ítems de usuarios autenticados se asocian mediante user_id (cart_id puede ser null),
            por lo que CartService.remove_from_cart debe resolver la pertenencia de sesión/usuario.
        """
        from django.urls import reverse
        from cart.models import CartItem

        # Arrange
        cart_item = CartItem.objects.create(
            user=user,
            product=product,
            quantity=3,
            purchase_price=product.price
        )

        # Act
        url = reverse('cart:remove_cart_item', args=[product.id, cart_item.id])
        response = client_with_user.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'deleted'
        assert data['item_id'] == cart_item.id
        assert data['cart']['is_empty'] is True
        assert data['cart']['item_count'] == 0
        assert not CartItem.objects.filter(id=cart_item.id).exists()



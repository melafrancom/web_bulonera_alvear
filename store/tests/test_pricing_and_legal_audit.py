from decimal import Decimal
import os
import re
import pytest
from django.test import TestCase, Client
from django.urls import reverse

from store.models import Product, Category
from store.services import PricingService
from cart.models import Cart, CartItem
from cart.services import CartService


class PricingServiceTests(TestCase):
    """Pruebas unitarias para PricingService y cálculo neto de la Resolución 4/2025."""

    def test_default_tax_rate_is_21_percent(self):
        # 121.00 bruto con 21% -> 100.00 neto
        net = PricingService.calculate_net_price(Decimal('121.00'))
        self.assertEqual(net, Decimal('100.00'))

    def test_custom_tax_rate_10_5_percent(self):
        # 110.50 bruto con 10.50% -> 100.00 neto
        net = PricingService.calculate_net_price(Decimal('110.50'), tax_rate=Decimal('10.50'))
        self.assertEqual(net, Decimal('100.00'))

    def test_zero_tax_rate_exento(self):
        net = PricingService.calculate_net_price(Decimal('500.00'), tax_rate=Decimal('0.00'))
        self.assertEqual(net, Decimal('500.00'))

    def test_half_up_rounding(self):
        # 100 / 1.21 = 82.644628... -> 82.64
        net = PricingService.calculate_net_price(100.00)
        self.assertEqual(net, Decimal('82.64'))

    def test_edge_cases_and_none(self):
        self.assertEqual(PricingService.calculate_net_price(None), Decimal('0.00'))
        self.assertEqual(PricingService.calculate_net_price(0), Decimal('0.00'))
        self.assertEqual(PricingService.calculate_net_price(-50), Decimal('0.00'))
        self.assertEqual(PricingService.calculate_net_price("invalid"), Decimal('0.00'))


class ProductNetPriceTests(TestCase):
    """Pruebas de propiedades de producto para precios sin impuestos nacionales."""

    def setUp(self):
        self.category = Category.objects.create(category_name="Fijaciones", slug="fijaciones")
        self.product_default = Product.objects.create(
            code="P-21",
            name="Bulón Hexagonal 1/2 x 2",
            slug="bulon-hex-1-2-x-2",
            price=1210.00,
            stock=100,
            category=self.category
        )
        self.product_10_5 = Product.objects.create(
            code="P-105",
            name="Máquina Eléctrica Taladro",
            slug="maquina-taladro-105",
            price=1105.00,
            tax_rate=Decimal('10.50'),
            stock=10,
            category=self.category
        )

    def test_product_default_effective_tax_rate(self):
        self.assertEqual(self.product_default.effective_tax_rate, Decimal('21.00'))
        self.assertEqual(self.product_default.price_without_taxes, Decimal('1000.00'))
        self.assertEqual(self.product_default.effective_price_without_taxes, Decimal('1000.00'))

    def test_product_custom_tax_rate(self):
        self.assertEqual(self.product_10_5.effective_tax_rate, Decimal('10.50'))
        self.assertEqual(self.product_10_5.price_without_taxes, Decimal('1000.00'))

    def test_product_on_sale_net_price(self):
        self.product_default.is_on_sale = True
        self.product_default.sale_price = 968.00  # 968 / 1.21 = 800.00
        self.product_default.save()

        self.assertEqual(self.product_default.sale_price_without_taxes, Decimal('800.00'))
        self.assertEqual(self.product_default.effective_price_without_taxes, Decimal('800.00'))


class CartNetPriceTests(TestCase):
    """Pruebas de desglose de precios netos en carrito."""

    def setUp(self):
        self.category = Category.objects.create(category_name="Herramientas", slug="herramientas")
        self.product = Product.objects.create(
            code="P-CART",
            name="Llave Combinada 13mm",
            slug="llave-combinada-13mm",
            price=1210.00,
            stock=50,
            category=self.category
        )
        self.cart = Cart.objects.create(cart_id="test-session-cart")
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
            purchase_price=Decimal('1210.00')
        )

    def test_cart_item_net_properties(self):
        self.assertEqual(self.cart_item.unit_price_without_taxes, Decimal('1000.00'))
        self.assertEqual(self.cart_item.sub_total, Decimal('2420.00'))
        self.assertEqual(self.cart_item.sub_total_without_taxes, Decimal('2000.00'))

    def test_cart_service_calculate_totals_includes_net_total(self):
        totals = CartService.calculate_cart_totals(CartItem.objects.filter(cart=self.cart))
        self.assertEqual(totals['total'], Decimal('2420.00'))
        self.assertEqual(totals['total_without_taxes'], Decimal('2000.00'))
        self.assertEqual(totals['quantity'], 2)


class TemplateAccessibilityAndLegalAuditTests(TestCase):
    """
    Auditoría estática de accesibilidad y textos legales sobre todas las plantillas.
    Garantiza que no reaparezcan textos 'sin imagen' ni promesas normativas divergentes.
    """

    def test_no_sin_imagen_or_unlabeled_img_in_any_template(self):
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates')
        violations = []
        for root, _, files in os.walk(templates_dir):
            for file in files:
                if file.endswith('.html'):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, templates_dir)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Chequear alt="sin imagen"
                    if re.search(r'alt\s*=\s*["\']sin imagen["\']', content, re.I):
                        violations.append(f"{rel_path}: contiene alt='sin imagen'")
                    
                    # Chequear <img> sin atributo alt
                    for m in re.finditer(r'<img\b[^>]*>', content, re.I):
                        tag = m.group(0)
                        if not re.search(r'(?:^|\s):?alt\s*=', tag, re.I):
                            violations.append(f"{rel_path}: <img> sin alt -> {tag[:80]}")

        self.assertEqual(violations, [], f"Violaciones de accesibilidad encontradas: {violations}")

    def test_footer_renders_legal_disclaimer(self):
        client = Client()
        response = client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Las fotos publicadas son a modo ilustrativo")
        self.assertContains(response, "sujeta a la verificación y confirmación de stock")
        self.assertContains(response, "www.buloneraalvear.online")

    def test_return_policy_statutory_24h_promise(self):
        client = Client()
        response = client.get(reverse('return_policy'))
        self.assertEqual(response.status_code, 200)
        # Disposición 954/2025, art. 5: plazo para informar código y adoptar medidas
        self.assertContains(response, "Disposición 954/2025, art. 5")
        self.assertContains(response, "dentro de las 24 horas")
        self.assertNotContains(response, "portada y en el pie de página")

    def test_terms_and_conditions_links_to_arrepentimiento(self):
        client = Client()
        response = client.get(reverse('terms_and_conditions'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('orders:arrepentimiento'))
        self.assertNotContains(response, "portada y pie de página")


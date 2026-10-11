"""
Suite de Pruebas de Carga para BULONERA WEB.
Implementa escenarios escalonados para evaluar la capacidad del backend Django + uWSGI + Redis + MariaDB.

REGLA: Este script se ejecuta dentro del contenedor oficial 'locustio/locust:2.32.8'.
POR QUÉ: Evita dependencias en el host y permite monitorear el consumo de CPU del generador vía Docker.
"""

import json
import logging
import os
import random
import re
from locust import HttpUser, task, between

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Carga de Parámetros y Fixtures de Prueba
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA_FILE = os.path.join(os.path.dirname(__file__), "test_data.json")

DEFAULT_DATA = {
    "categories": ["buloneria", "ferreteria"],
    "subcategories": [
        {"category": "buloneria", "subcategory": "tornillos-autoperforantes"},
        {"category": "buloneria", "subcategory": "arandelas"},
        {"category": "ferreteria", "subcategory": "mangueras"},
    ],
    "products": [
        {"id": 26791, "slug": "cano-riego-tricolor-super-reforzado-34-x-50"},
        {"id": 26792, "slug": "cano-riego-cristal-reforzado-verde-12-x-50"},
    ],
    "search_terms": ["cano", "riego", "bulon", "arandela", "tornillo"],
    "blog_posts": ["historia", "post-de-prueba-publicacion-admin-552"],
}

try:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            TEST_DATA = json.load(f)
    else:
        TEST_DATA = DEFAULT_DATA
except Exception as e:
    logger.warning(f"No se pudo cargar test_data.json ({e}). Usando valores por defecto.")
    TEST_DATA = DEFAULT_DATA


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FASE A1: Navegación de Catálogo (con Sesión Inicial)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CatalogUser(HttpUser):
    """
    Simula navegación de catálogo y lectura de contenido.
    POR QUÉ: En el detalle de producto (/p/<slug>/), _cart_id() crea una sesión
    anónima inicial en django_session para cada usuario virtual nuevo.
    Objetivo: Medir el rendimiento del renderizado de plantillas, eficiencia de Redis
    y costo de creación inicial de sesiones en base de datos.
    """
    # Think time realista: 3 a 6 segundos entre clicks
    wait_time = between(3, 6)

    @task(25)
    def view_home(self):
        """# 1. Portada principal con banners y destacados."""
        self.client.get("/", name="/ (Home)")

    @task(30)
    def view_category(self):
        """# 2. Listado de productos por categoría."""
        categories = TEST_DATA.get("categories", ["buloneria"])
        category_slug = random.choice(categories)
        self.client.get(
            f"/store/category/{category_slug}/",
            name="/store/category/[category_slug]/"
        )

    @task(10)
    def view_subcategory(self):
        """# 3. Listado de productos por subcategoría."""
        subcategories = TEST_DATA.get("subcategories", [])
        if subcategories:
            item = random.choice(subcategories)
            cat = item.get("category", "buloneria")
            sub = item.get("subcategory", "tornillos-autoperforantes")
            self.client.get(
                f"/store/category/{cat}/subcategory/{sub}/",
                name="/store/category/[cat]/subcategory/[sub]/"
            )

    @task(25)
    def view_product_detail(self):
        """# 4. Detalle de producto individual."""
        products = TEST_DATA.get("products", [{"slug": "tornillo-autoperforante-hexagonal"}])
        product = random.choice(products)
        slug = product.get("slug", "producto")
        self.client.get(
            f"/p/{slug}/",
            name="/p/[product_slug]/"
        )

    @task(5)
    def view_blog_list(self):
        """# 5. Listado de artículos del blog."""
        self.client.get("/blog/", name="/blog/ (List)")

    @task(5)
    def view_blog_post(self):
        """# 6. Lectura de artículo del blog."""
        posts = TEST_DATA.get("blog_posts", ["guia-seleccion-bulones-industriales"])
        post_slug = random.choice(posts)
        self.client.get(
            f"/blog/{post_slug}/",
            name="/blog/[post_slug]/"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FASE A2: Búsqueda de Productos (Con Mutaciones en BD)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SearchUser(HttpUser):
    """
    Simula usuarios realizando búsquedas con palabras clave.
    POR QUÉ: SearchService.register_search_results inserta hasta 8 registros
    en ProductSearch por búsqueda. Se aísla para medir el impacto de estas escrituras en MariaDB.
    """
    wait_time = between(4, 7)

    @task(100)
    def search_keyword(self):
        """Ejecuta búsqueda con palabra clave aleatoria."""
        terms = TEST_DATA.get("search_terms", ["tornillo", "bulon"])
        term = random.choice(terms)
        self.client.get(
            f"/store/search/?keyword={term}",
            name="/store/search/?keyword=[term]"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FASE B: Carrito de Compras (Transaccional Ligera)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CartUser(HttpUser):
    """
    Simula interacción con el carrito de compras (GET producto → POST add_cart → GET ver carrito).
    REGLA: Requiere conservar cookies de sesión, token CSRF y cabecera Referer válida.
    """
    wait_time = between(4, 8)

    def _extract_csrf_token(self, response_text: str) -> str:
        """
        Extrae el token CSRF desde la cookie de sesión o desde el HTML del formulario.
        """
        # 1. Intentar desde la cookie
        cookie_token = self.client.cookies.get("csrftoken")
        if cookie_token:
            return cookie_token

        # 2. Fallback: extraer desde el input hidden del template Django
        match = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', response_text)
        if match:
            return match.group(1)
        return ""

    @task(80)
    def add_to_cart_flow(self):
        """
        Flujo de agregado al carrito:
        1. GET a la página del producto para obtener sesión y CSRF token.
        2. POST a /cart/add_cart/<id>/ con Referer y CSRF.
        """
        products = TEST_DATA.get("products", [{"id": 1, "slug": "tornillo-autoperforante-hexagonal"}])
        product = random.choice(products)
        product_id = product.get("id", 1)
        product_slug = product.get("slug", "producto")

        # Paso 1: Visitar producto
        product_url = f"/p/{product_slug}/"
        resp = self.client.get(product_url, name="/p/[product_slug]/ (Pre-cart)")
        csrf_token = self._extract_csrf_token(resp.text)

        # Paso 2: POST para agregar al carrito
        headers = {
            "Referer": f"{self.host}{product_url}",
            "X-CSRFToken": csrf_token,
        }
        data = {
            "quantity": 1,
            "csrfmiddlewaretoken": csrf_token
        }

        self.client.post(
            f"/cart/add_cart/{product_id}/",
            data=data,
            headers=headers,
            name="/cart/add_cart/[product_id]/"
        )

    @task(20)
    def view_cart(self):
        """Visualización del contenido del carrito."""
        self.client.get("/cart/", name="/cart/ (View)")

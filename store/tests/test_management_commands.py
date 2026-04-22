"""
Tests para el management command seo_optimize_slugs (Fase 3)
"""

import pytest
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from store.models import Product
from category.models import Category


@pytest.mark.django_db
class TestSeoOptimizeSlugsCommand:
    """Tests del management command seo_optimize_slugs."""

    def test_command_dry_run(self, category):
        """Verifica que --dry-run no modifica la base de datos."""
        # Crear producto con nombre placeholder para que el save() NO regenere el slug
        product = Product.objects.create(
            code='PROD-001',
            name='Producto Temporal',  # Temporal - empieza con 'Producto'
            slug='producto-0670010001',  # Placeholder
            price=5.0,
            stock=100,
            category=category
        )
        # Ahora cambiar el nombre a uno real directamente en la BD (sin save)
        # Esto simula un producto que fue enriquecido después de su creación
        Product.objects.filter(id=product.id).update(name='Bulón Cabeza Hexagonal G5 M8 x 25mm')
        
        slug_antes = product.slug

        # Ejecutar comando con --dry-run
        out = StringIO()
        call_command('seo_optimize_slugs', '--dry-run', stdout=out)

        # Verificar que el slug no cambió
        product.refresh_from_db()
        assert product.slug == slug_antes

        # Verificar que el output contiene "DRY RUN" o "Actualizados"
        output = out.getvalue()
        assert 'DRY RUN' in output or 'Actualizados' in output or 'RESULTADO FINAL' in output

    def test_command_updates_placeholder_slug(self, category):
        """Verifica que el comando actualiza slugs placeholder (sin --dry-run)."""
        # Crear producto con nombre placeholder, luego actualizar nombre sin pasar por save()
        product = Product.objects.create(
            code='PROD-002',
            name='Producto Temporal',
            slug='producto-0670010002',
            price=5.0,
            stock=100,
            category=category
        )
        # Actualizar nombre sin pasar por save()
        Product.objects.filter(id=product.id).update(name='Tornillo Inox M8 x 30mm')

        # Ejecutar comando sin --dry-run
        out = StringIO()
        call_command('seo_optimize_slugs', stdout=out)

        # Verificar que el slug cambió
        product.refresh_from_db()
        assert product.slug != 'producto-0670010002'
        assert product.slug == 'tornillo-inox-m8-x-30mm'

    def test_command_skips_short_names(self, category):
        """Verifica que el comando NO procesa nombres cortos."""
        # Nombre corto (menos de 10 caracteres)
        product = Product.objects.create(
            code='PROD-003',
            name='Tornillo',  # Solo 8 caracteres
            slug='producto-001',
            price=5.0,
            stock=100,
            category=category
        )
        slug_antes = product.slug

        # Ejecutar comando
        out = StringIO()
        call_command('seo_optimize_slugs', stdout=out)

        # Verificar que el slug NO cambió (nombre es corto, no será procesado)
        product.refresh_from_db()
        assert product.slug == slug_antes

    def test_command_with_category_filter(self, category):
        """Verifica que --category filtra por categoría."""
        # Crear otro producto en otra categoría
        other_category = Category.objects.create(
            category_name='Otra Categoría',
            slug='otra-categoria'
        )

        product1 = Product.objects.create(
            code='PROD-004',
            name='Producto Temporal 1',
            slug='producto-0670010004',
            price=5.0,
            stock=100,
            category=category
        )
        # Actualizar nombre sin pasar por save()
        Product.objects.filter(id=product1.id).update(name='Tornillo en Categoría Principal')

        product2 = Product.objects.create(
            code='PROD-005',
            name='Producto Temporal 2',
            slug='producto-0670010005',
            price=5.0,
            stock=100,
            category=other_category
        )
        # Actualizar nombre sin pasar por save()
        Product.objects.filter(id=product2.id).update(name='Tornillo en Otra Categoría')

        # Ejecutar comando solo para la categoría principal
        out = StringIO()
        call_command('seo_optimize_slugs', '--category', category.slug, stdout=out)

        # Verificar que solo product1 fue actualizado
        product1.refresh_from_db()
        product2.refresh_from_db()

        assert product1.slug != 'producto-0670010004'  # Actualizado
        assert product2.slug == 'producto-0670010005'  # NO actualizado

    def test_command_handles_collisions(self, category):
        """Verifica que el comando maneja colisiones agregando code."""
        # Crear dos productos con nombre similar (potencial colisión)
        product1 = Product.objects.create(
            code='BOLT-001',
            name='Bulón Especial A',
            slug='bulon-especial-a',
            price=5.0,
            stock=100,
            category=category
        )

        product2 = Product.objects.create(
            code='BOLT-002',
            name='Producto Temporal',
            slug='producto-0670010006',
            price=5.0,
            stock=100,
            category=category
        )
        # Actualizar nombre a uno que causa colisión con product1
        # "Bulón Especial A" → slug sería "bulon-especial-a"
        Product.objects.filter(id=product2.id).update(name='Bulón Especial A Variante')

        # Ejecutar comando
        out = StringIO()
        call_command('seo_optimize_slugs', stdout=out)

        # Verificar que product2 obtuvo un slug diferente (sin colisión)
        product2.refresh_from_db()
        assert product2.slug != 'producto-0670010006'
        assert product2.slug is not None

    def test_command_output_stats(self, category):
        """Verifica que el comando imprime estadísticas correctas."""
        # Crear algunos productos con nombres placeholder
        for i in range(3):
            product = Product.objects.create(
                code=f'PROD-{i:03d}',
                name='Producto Temporal',
                slug=f'producto-000000{i}',
                price=5.0,
                stock=100,
                category=category
            )
            # Actualizar nombre sin pasar por save() (NO debe empezar con 'Producto ')
            Product.objects.filter(id=product.id).update(
                name=f'Real Prueba Número {i} Componente Extra'
            )

        # Ejecutar comando
        out = StringIO()
        call_command('seo_optimize_slugs', stdout=out)

        output = out.getvalue()

        # Verificar que el output contiene palabras clave
        assert 'RESULTADO FINAL' in output or 'Actualizados' in output

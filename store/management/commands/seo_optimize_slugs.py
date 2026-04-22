"""
Management Command: seo_optimize_slugs

Fase 3 - SEO URL Refactoring & Slug Healing

Regenera slugs inteligentemente para productos con nombres reales pero slugs placeholder.
Maneja colisiones agregando el código como sufijo.

Uso:
    # Siempre primero: validar sin guardar cambios
    docker-compose exec web python manage.py seo_optimize_slugs --dry-run
    
    # Procesar una categoría específica
    docker-compose exec web python manage.py seo_optimize_slugs --category buloneria
    
    # Procesar todo
    docker-compose exec web python manage.py seo_optimize_slugs
    
    # Procesar con batch size personalizado
    docker-compose exec web python manage.py seo_optimize_slugs --batch-size 500
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from store.models import Product
from category.models import Category
from django.db.models import Q


class Command(BaseCommand):
    help = 'Regenera slugs inteligentemente para productos con nombres reales pero slugs placeholder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la ejecución sin guardar cambios'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Procesa solo una categoría (por slug). Ejemplo: buloneria'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenera slugs aunque no sean placeholder (requiere confirmación)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Productos por lote (control de RAM). Default: 200'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        category_slug = options['category']
        force = options['force']
        batch_size = options['batch_size']

        # Validar batch_size
        if batch_size <= 0:
            raise CommandError('--batch-size debe ser mayor a 0')

        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('🔍 Escaneando productos con slugs placeholder...'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        # Construir filtros
        filters = Q(
            name__isnull=False,
            slug__startswith='producto-'
        ) & ~Q(name__startswith='Producto ')

        # Nota: No agregamos filtro de longitud aquí porque SQLite no soporta __length
        # Lo haremos en memoria más abajo

        # Filtrar por categoría si se especifica
        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
                filters = filters & Q(category=category)
                self.stdout.write(f'📂 Categoría: {category.category_name}')
            except Category.DoesNotExist:
                raise CommandError(f'Categoría "{category_slug}" no encontrada')

        # Obtener candidatos
        candidates = Product.objects.filter(filters).values_list('id', 'name', 'slug', 'code').order_by('id')
        total_candidates = candidates.count()

        if total_candidates == 0:
            self.stdout.write(self.style.WARNING('⏭  No hay productos para procesar'))
            return

        self.stdout.write(self.style.SUCCESS(f'   Encontrados: {total_candidates:,} candidatos\n'))

        # Estadísticas
        stats = {
            'updated': 0,
            'collisions': 0,
            'skipped': 0,
            'errors': 0,
        }

        # Procesar en lotes
        total_lotes = (total_candidates + batch_size - 1) // batch_size
        candidatos_procesados = 0
        
        # Obtener todos los IDs en memoria (evita problema de MariaDB con LIMIT en subqueries)
        all_ids = list(candidates.values_list('id', flat=True))

        for lote_num in range(1, total_lotes + 1):
            inicio = (lote_num - 1) * batch_size
            fin = inicio + batch_size
            
            # IDs del lote actual
            lote_ids = all_ids[inicio:fin]

            self.stdout.write(
                self.style.WARNING(f'\n▶ Procesando lote {lote_num}/{total_lotes} '
                                 f'(productos {inicio + 1}-{min(fin, total_candidates)})...')
            )

            # Obtener productos del lote sin usar subquery con LIMIT
            lote_productos = Product.objects.filter(id__in=lote_ids)

            for product in lote_productos:
                candidatos_procesados += 1
                slug_anterior = product.slug

                # Filtrar por longitud del nombre si no es --force
                if not force and len(product.name) <= 10:
                    stats['skipped'] += 1
                    self.stdout.write(
                        f'   ⏭  {slug_anterior} (nombre aún corto, < 10 caracteres)'
                    )
                    continue

                try:
                    # Generar nuevo slug
                    nuevo_slug = self._generar_nuevo_slug(product)

                    # Si el slug no cambió, omitir
                    if nuevo_slug == slug_anterior:
                        stats['skipped'] += 1
                        self.stdout.write(
                            f'   ⏭  {slug_anterior} (sin cambios, nombre aún placeholder?)'
                        )
                        continue

                    # Detectar si hubo colisión
                    hubo_colision = '-' in nuevo_slug and product.code and slugify(product.code) in nuevo_slug

                    if dry_run:
                        if hubo_colision:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'   ⚠  {slug_anterior} → {nuevo_slug} '
                                    f'[colisión, usando: {nuevo_slug}]'
                                )
                            )
                            stats['collisions'] += 1
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'   ✓ {slug_anterior} → {nuevo_slug}')
                            )
                        stats['updated'] += 1
                    else:
                        # Actualizar slug
                        product.slug = nuevo_slug
                        product.save(update_fields=['slug', 'modified_date'])

                        if hubo_colision:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'   ⚠  {slug_anterior} → {nuevo_slug} '
                                    f'[colisión, usando: {nuevo_slug}]'
                                )
                            )
                            stats['collisions'] += 1
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'   ✓ {slug_anterior} → {nuevo_slug}')
                            )
                        stats['updated'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ {product.slug} - Error: {str(e)}')
                    )

        # Resumen final
        self.stdout.write('\n' + self.style.WARNING('='*70))
        self.stdout.write(self.style.SUCCESS('📊 RESULTADO FINAL'))
        self.stdout.write(self.style.WARNING('='*70))

        self.stdout.write(self.style.SUCCESS(f'✅ Actualizados:       {stats["updated"]:,}'))
        self.stdout.write(self.style.WARNING(f'⚠  Con colisión:         {stats["collisions"]:,}'))
        self.stdout.write(f'⏭  Omitidos:              {stats["skipped"]:,}')
        self.stdout.write(self.style.ERROR(f'❌ Errores:                {stats["errors"]:,}'))
        self.stdout.write(self.style.WARNING('='*70 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN - No se guardaron cambios\n'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Cambios guardados exitosamente\n'))

    def _generar_nuevo_slug(self, product):
        """
        Genera un slug único para el producto. Si hay colisión, agrega code como sufijo.
        Lógica idéntica a _generate_unique_slug() en el modelo.
        """
        if not product.name:
            return product.slug or 'producto'

        base_slug = slugify(product.name)
        if not base_slug:
            return product.slug or 'producto'

        # Verificar colisión excluyendo el producto actual
        qs = Product.objects.filter(slug=base_slug).exclude(pk=product.pk)
        if not qs.exists():
            return base_slug

        # Colisión: agregar code como desambiguador
        if product.code:
            slug_with_code = f"{base_slug}-{slugify(product.code)}"
            qs2 = Product.objects.filter(slug=slug_with_code).exclude(pk=product.pk)
            if not qs2.exists():
                return slug_with_code

        # Fallback final: mantener slug actual para no romper nada
        return product.slug

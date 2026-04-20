"""
Management command para deduplicar y limpiar productos con códigos corruptos (*.0).

Este script identifica productos cuyo código termina en .0 (resultado de importación
fallida de Pandas), migra sus assets (ProductGallery, imágenes, categorías) al producto
limpio (sin .0) y elimina el registro corrupto.

Usar con transacciones para rollback seguro en caso de error.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from store.models import Product, ProductGallery

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deduplicar productos corruptos (código terminado en .0) y migrar sus assets"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo seco (sin cambios en BD)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar logs detallados',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        try:
            # Encontrar productos con código terminado en .0
            corrupted_products = Product.objects.filter(code__endswith='.0')
            count = corrupted_products.count()
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('✓ No hay productos corruptos (*.0) para limpiar'))
                return
            
            self.stdout.write(
                self.style.WARNING(f'⚠ Se encontraron {count} productos corruptos (*.0)')
            )
            
            if dry_run:
                self.stdout.write(self.style.NOTICE('🔍 Modo DRY-RUN: No se realizarán cambios'))
                self._dry_run_analysis(corrupted_products)
            else:
                self.stdout.write(self.style.NOTICE('▶ Iniciando deduplicación...'))
                self._deduplicate(corrupted_products, verbose)
                self.stdout.write(self.style.SUCCESS('✓ Deduplicación completada'))
        
        except Exception as e:
            logger.error(f"Error en deduplicación: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            raise CommandError(str(e))
    
    def _dry_run_analysis(self, corrupted_products):
        """Análisis de productos corruptos sin hacer cambios"""
        total_gallery = 0
        total_subcategories = 0
        migrate_possible = 0
        not_found = 0
        
        for product in corrupted_products:
            clean_code = product.code.replace('.0', '')
            clean_product = Product.objects.filter(code=clean_code).first()
            
            gallery_count = product.productgallery_set.count()
            subcategories_count = product.subcategories.count()
            has_image = bool(product.images)
            
            total_gallery += gallery_count
            total_subcategories += subcategories_count
            
            if clean_product:
                migrate_possible += 1
                self.stdout.write(
                    f"  ✓ {product.code} → {clean_code}: "
                    f"Gallery={gallery_count}, Subs={subcategories_count}, Image={has_image}"
                )
            else:
                not_found += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ✗ {product.code}: Código limpio {clean_code} NO EXISTE"
                    )
                )
        
        self.stdout.write(f'\n📊 RESUMEN:')
        self.stdout.write(f'   Total corruptos: {corrupted_products.count()}')
        self.stdout.write(f'   Pueden migrarse: {migrate_possible}')
        self.stdout.write(f'   Sin código limpio: {not_found}')
        self.stdout.write(f'   Total galería: {total_gallery}')
        self.stdout.write(f'   Total subcategorías: {total_subcategories}')
    
    @transaction.atomic
    def _deduplicate(self, corrupted_products, verbose):
        """Deduplicar con transacción atómica"""
        migrated = 0
        skipped = 0
        errors = []
        
        for product in corrupted_products:
            try:
                clean_code = product.code.replace('.0', '')
                clean_product = Product.objects.filter(code=clean_code).first()
                
                if not clean_product:
                    msg = f"Código limpio {clean_code} NO EXISTE para {product.code}"
                    errors.append((product.code, msg))
                    skipped += 1
                    logger.warning(msg)
                    continue
                
                # Migrar ProductGallery
                gallery_items = product.productgallery_set.all()
                gallery_count = gallery_items.count()
                for gallery in gallery_items:
                    gallery.product = clean_product
                    gallery.save()
                
                # Migrar imagen principal si el producto limpio no la tiene
                if product.images and not clean_product.images:
                    clean_product.images = product.images
                    clean_product.save(update_fields=['images'])
                
                # Migrar subcategorías
                clean_product.subcategories.add(*product.subcategories.all())
                
                # Eliminar producto corrupto
                product_id = product.id
                product.delete()
                
                migrated += 1
                if verbose:
                    self.stdout.write(
                        f"  ✓ {clean_code}: Migró {gallery_count} galería, subcategorías, imagen"
                    )
                logger.info(f"Deduplicado: {clean_code} (eliminó ID={product_id})")
            
            except Exception as e:
                errors.append((product.code, str(e)))
                skipped += 1
                logger.error(f"Error deduplicando {product.code}: {e}", exc_info=True)
        
        # Resumen
        self.stdout.write(f'\n📊 RESULTADOS:')
        self.stdout.write(self.style.SUCCESS(f'   ✓ Migraciones exitosas: {migrated}'))
        self.stdout.write(self.style.WARNING(f'   ⚠ Omitidos/Errores: {skipped}'))
        
        if errors:
            self.stdout.write(self.style.ERROR(f'\n❌ ERRORES:'))
            for code, error in errors:
                self.stdout.write(f'   {code}: {error}')

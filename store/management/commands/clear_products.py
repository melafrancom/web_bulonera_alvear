"""
Management command para limpiar completamente el catálogo de productos.

Este script elimina TODOS los productos, sus galerías, búsquedas asociadas y
cualquier relación en cascada. Está diseñado como alternativa al Django Admin
para evitar el límite DATA_UPLOAD_MAX_NUMBER_FIELDS en operaciones masivas.

⚠️ OPERACIÓN DESTRUCTIVA: Pide confirmación explícita del usuario.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from store.models import Product, ProductGallery, ProductSearch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "🗑️ Eliminar TODOS los productos del catálogo (requiere confirmación)"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ejecutar sin pedir confirmación (NO recomendado)',
        )
    
    def handle(self, *args, **options):
        force = options.get('force', False)
        
        try:
            # Contar productos actuales
            product_count = Product.objects.count()
            gallery_count = ProductGallery.objects.count()
            search_count = ProductSearch.objects.count()
            
            if product_count == 0:
                self.stdout.write(self.style.SUCCESS('✓ El catálogo ya está vacío (0 productos)'))
                return
            
            # Mostrar advertencia
            self.stdout.write(self.style.ERROR(
                f'\n⚠️  ALERTA CRÍTICA - OPERACIÓN DESTRUCTIVA ⚠️\n'
                f'Está a punto de eliminar:\n'
                f'  • {product_count} productos\n'
                f'  • {gallery_count} registros de galería\n'
                f'  • {search_count} registros de búsqueda\n'
                f'\nEsta acción es IRREVERSIBLE sin restaurar desde backup.\n'
            ))
            
            # Pedir confirmación
            if not force:
                confirmation = input('¿Deseas continuar? Escribe "S" para confirmar: ').strip().upper()
                if confirmation != 'S':
                    self.stdout.write(self.style.WARNING('❌ Operación cancelada por el usuario'))
                    return
            
            # Ejecutar limpieza en transacción atómica
            self.stdout.write('▶ Iniciando limpieza del catálogo...')
            
            with transaction.atomic():
                # Eliminar productos (cascada automática limpia ProductGallery, etc.)
                deleted_count, deleted_dict = Product.objects.all().delete()
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ LIMPIEZA COMPLETADA:\n'
                    f'   {product_count} productos eliminados\n'
                    f'   {deleted_count} registros totales borrados en cascada\n'
                ))
                
                # Verificación final
                remaining = Product.objects.count()
                if remaining == 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Base de datos limpia. Productos restantes: {remaining}'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'⚠️  Advertencia: {remaining} productos quedan en la DB'
                    ))
        
        except Exception as e:
            logger.error(f"Error en limpieza de catálogo: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            raise CommandError(str(e))

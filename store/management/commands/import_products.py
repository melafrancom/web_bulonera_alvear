"""
Management command para importar productos desde Excel/CSV
"""
from django.core.management.base import BaseCommand, CommandError
from store.services import ProductService
import os


class Command(BaseCommand):
    help = 'Importa productos desde Excel/CSV exportado del ERP'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'filepath',
            type=str,
            help='Ruta al archivo Excel (.xlsx) o CSV (.csv) a importar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la importación sin guardar cambios en la base de datos'
        )
        parser.add_argument(
            '--update-prices',
            action='store_true',
            help='Solo actualiza precios de productos existentes'
        )
    
    def handle(self, *args, **options):
        filepath = options['filepath']
        dry_run = options['dry_run']
        update_prices = options['update_prices']
        
        # Validar que el archivo existe
        if not os.path.exists(filepath):
            raise CommandError(f'El archivo no existe: {filepath}')
        
        # Validar extensión
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ['.xlsx', '.csv']:
            raise CommandError(f'Formato de archivo no soportado: {ext}. Use .xlsx o .csv')
        
        self.stdout.write(self.style.WARNING(f'Iniciando importación desde: {filepath}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se guardarán cambios'))
        
        try:
            if update_prices:
                self.stdout.write('Actualizando solo precios...')
                result = ProductService.update_prices_from_file(filepath)
            else:
                result = ProductService.import_from_file(
                    filepath,
                    dry_run=dry_run,
                    update_prices=False
                )
            
            # Mostrar resultados
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('RESUMEN DE IMPORTACIÓN'))
            self.stdout.write('='*60)
            
            if update_prices:
                self.stdout.write(f'Precios actualizados: {result.updated}')
            else:
                self.stdout.write(f'Productos creados: {result.created}')
                self.stdout.write(f'Productos actualizados: {result.updated}')
            
            if result.errors > 0:
                self.stdout.write(self.style.ERROR(f'Errores: {result.errors}'))
            
            if result.image_warnings > 0:
                self.stdout.write(self.style.WARNING(f'Advertencias de imagen: {result.image_warnings}'))
            
            # Mostrar detalles de errores
            if result.error_details:
                self.stdout.write('\n' + self.style.ERROR('DETALLES DE ERRORES:'))
                for row, msg in result.error_details[:10]:  # Mostrar primeros 10
                    self.stdout.write(f'  Fila {row}: {msg}')
                
                if len(result.error_details) > 10:
                    self.stdout.write(f'  ... y {len(result.error_details) - 10} errores más')
            
            self.stdout.write('='*60 + '\n')
            
            if result.errors == 0:
                self.stdout.write(self.style.SUCCESS('✓ Importación completada exitosamente'))
            else:
                self.stdout.write(self.style.WARNING('⚠ Importación completada con errores'))
            
        except Exception as e:
            raise CommandError(f'Error durante la importación: {str(e)}')

"""Management command para importar imágenes existentes al banco de imágenes"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from media_bank.models import ImageAsset, ImageType, UPLOAD_PATHS


class Command(BaseCommand):
    help = (
        'Importa imágenes existentes desde disco al banco de imágenes. '
        'NUEVO en Fase A: Acepta --type para especificar el tipo de imagen.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['product', 'category', 'subcategory', 'carousel'],
            default='product',
            help='Tipo de imagen a importar (default: product)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la importación sin crear registros en la base de datos',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        image_type = options.get('type', 'product')
        
        # Obtener ruta según tipo
        type_path = UPLOAD_PATHS.get(image_type, 'photos/products/original/')
        images_dir = os.path.join(settings.MEDIA_ROOT, type_path)
        
        self.stdout.write(
            self.style.SUCCESS(f'📁 Importando imágenes tipo: {image_type}')
        )
        self.stdout.write(f'   Directorio: {images_dir}')
        
        if not os.path.exists(images_dir):
            self.stdout.write(
                self.style.WARNING(f'El directorio {images_dir} no existe. Creándolo...')
            )
            os.makedirs(images_dir, exist_ok=True)
            return
        
        # Extensiones de imagen válidas
        valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
        
        imported_count = 0
        skipped_count = 0
        
        # Recorrer archivos en el directorio
        for filename in os.listdir(images_dir):
            if not filename.lower().endswith(valid_extensions):
                continue
            
            file_path = os.path.join(type_path, filename)
            
            # Verificar si ya existe en la base de datos (idempotencia)
            if ImageAsset.objects.filter(file=file_path, image_type=image_type).exists():
                self.stdout.write(
                    self.style.WARNING(f'   Ya existe: {filename}')
                )
                skipped_count += 1
                continue
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'   [DRY RUN] Importaría: {filename}')
                )
                imported_count += 1
            else:
                # Crear el registro en la base de datos
                asset = ImageAsset.objects.create(
                    file=file_path,
                    image_type=image_type,
                    name=os.path.splitext(filename)[0]
                )
                self.stdout.write(
                    self.style.SUCCESS(f'   ✓ Importado: {filename} (ID: {asset.id})')
                )
                imported_count += 1
        
        # Resumen
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ [DRY RUN] Se importarían {imported_count} imágenes tipo "{image_type}"'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Importación completada: {imported_count} imágenes importadas'
                )
            )
        self.stdout.write(f'⏭️  Omitidas (ya existentes): {skipped_count}')
        self.stdout.write('='*60)

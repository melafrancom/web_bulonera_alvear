"""
Management command para re-procesar ImageAssets existentes y generar WebP.

Uso:
    # Reprocessar todos los assets
    docker-compose exec bulonera_web python manage.py reprocess_assets

    # Reprocessar solo banners
    docker-compose exec bulonera_web python manage.py reprocess_assets --type banner

    # Reprocessar solo categorías
    docker-compose exec bulonera_web python manage.py reprocess_assets --type category

    # Preview de cambios (sin ejecutar realmente)
    docker-compose exec bulonera_web python manage.py reprocess_assets --dry-run
"""

from django.core.management.base import BaseCommand
from media_bank.models import ImageAsset, ImageType


class Command(BaseCommand):
    help = "Re-procesa ImageAssets existentes para generar WebP faltantes"

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default=None,
            help="Filtrar por tipo: product, carousel, banner, category, subcategory",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Preview de cambios sin ejecutar",
        )

    def handle(self, *args, **options):
        image_type = options.get('type', None)
        dry_run = options.get('dry_run', False)

        # Construir query
        queryset = ImageAsset.objects.all()
        if image_type:
            queryset = queryset.filter(image_type=image_type)

        count = queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Se procesarían {count} assets"
                )
            )
            if count > 0:
                self.stdout.write("\nPrimeros 5 assets a procesar:")
                for asset in queryset[:5]:
                    self.stdout.write(
                        f"  - {asset.name or asset.file.name} ({asset.image_type})"
                    )
            return

        if count == 0:
            self.stdout.write(
                self.style.WARNING("No se encontraron assets para procesar")
            )
            return

        # Confirmar antes de ejecutar
        self.stdout.write(
            self.style.WARNING(f"Se procesarán {count} assets")
        )
        confirm = input("¿Deseas continuar? (s/n): ").lower()
        if confirm != 's':
            self.stdout.write(self.style.ERROR("Operación cancelada"))
            return

        # Procesar
        from store.tasks import process_image_asset_task

        processed = 0
        failed = 0

        for asset in queryset:
            try:
                process_image_asset_task.delay(asset.id)
                processed += 1
                self.stdout.write(
                    f"  ✓ Encolado: {asset.name or asset.file.name} ({asset.image_type})"
                )
            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Error: {asset.name or asset.file.name}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompletado: {processed} encolados, {failed} errores"
            )
        )

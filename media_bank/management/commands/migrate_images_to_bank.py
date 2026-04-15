"""
Management command para migrar imágenes existentes a ImageAsset.
Recorre todos los modelos que tenían imágenes directas y crea registros en ImageAsset.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from media_bank.models import ImageAsset, ImageType
from store.models import Product, ProductGallery, CarouselImage
from category.models import Category, SubCategory
import os


class Command(BaseCommand):
    help = 'Migra imágenes existentes a ImageAsset (Banco de Imágenes). Fase A de centralización.'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Simula la migración sin hacer cambios reales.',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  Modo DRY-RUN: No se harán cambios.'))
        
        try:
            with transaction.atomic():
                stats = {
                    'products': 0,
                    'gallery': 0,
                    'categories': 0,
                    'subcategories': 0,
                    'carousel': 0,
                    'duplicates': 0,
                }
                
                # 1. Migrar imágenes de Product
                self.stdout.write(self.style.SUCCESS('\n📦 Procesando Products...'))
                stats['products'] = self._migrate_products(dry_run)
                
                # 2. Migrar imágenes de ProductGallery
                self.stdout.write(self.style.SUCCESS('\n🖼️  Procesando ProductGallery...'))
                stats['gallery'] = self._migrate_gallery(dry_run)
                
                # 3. Migrar imágenes de Category
                self.stdout.write(self.style.SUCCESS('\n📂 Procesando Categories...'))
                stats['categories'] = self._migrate_categories(dry_run)
                
                # 4. Migrar imágenes de SubCategory
                self.stdout.write(self.style.SUCCESS('\n📂 Procesando SubCategories...'))
                stats['subcategories'] = self._migrate_subcategories(dry_run)
                
                # 5. Migrar imágenes de CarouselImage
                self.stdout.write(self.style.SUCCESS('\n🎠 Procesando CarouselImages...'))
                stats['carousel'] = self._migrate_carousel(dry_run)
                
                # Ejecutar rollback si es dry-run
                if dry_run:
                    raise Exception('DRY-RUN: Revirtiendo cambios...')
                
        except Exception as e:
            if dry_run and 'DRY-RUN' in str(e):
                self.stdout.write(self.style.SUCCESS('✅ Dry-run completado. Resumen:'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
                raise
        
        # Mostrar resumen
        self._print_summary(stats, dry_run)
    
    def _migrate_products(self, dry_run):
        """Migra imágenes de Product."""
        count = 0
        products = Product.objects.filter(images__isnull=False).exclude(images='')
        self.stdout.write(f"   Encontrados {products.count()} productos con imágenes legacy")
        
        for product in products:
            if self._create_or_get_image_asset(
                file_field=product.images,
                image_type=ImageType.PRODUCT,
                name=f"{product.code}-{product.name}",
                alt_text=product.image_alt,
                dry_run=dry_run
            ):
                if not dry_run:
                    asset = self._get_existing_asset(product.images.name, ImageType.PRODUCT)
                    if asset:
                        product.image = asset
                        product.save(update_fields=['image'])
                count += 1
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'   ✓ {count} productos migraron exitosamente'))
        return count
    
    def _migrate_gallery(self, dry_run):
        """Migra imágenes de ProductGallery."""
        count = 0
        gallery_items = ProductGallery.objects.filter(image__isnull=False).exclude(image='')
        self.stdout.write(f"   Encontrados {gallery_items.count()} items de galería con imágenes legacy")
        
        for item in gallery_items:
            if self._create_or_get_image_asset(
                file_field=item.image,
                image_type=ImageType.PRODUCT,
                name=f"{item.product.code}-gallery",
                alt_text=item.alt,
                dry_run=dry_run
            ):
                if not dry_run:
                    asset = self._get_existing_asset(item.image.name, ImageType.PRODUCT)
                    if asset:
                        item.image_asset = asset
                        item.save(update_fields=['image_asset'])
                count += 1
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'   ✓ {count} items de galería migraron exitosamente'))
        return count
    
    def _migrate_categories(self, dry_run):
        """Migra imágenes de Category."""
        count = 0
        categories = Category.objects.filter(cat_image__isnull=False).exclude(cat_image='')
        self.stdout.write(f"   Encontrados {categories.count()} categorías con imágenes legacy")
        
        for category in categories:
            if self._create_or_get_image_asset(
                file_field=category.cat_image,
                image_type=ImageType.CATEGORY,
                name=category.category_name,
                alt_text=f"Imagen de categoría: {category.category_name}",
                dry_run=dry_run
            ):
                if not dry_run:
                    asset = self._get_existing_asset(category.cat_image.name, ImageType.CATEGORY)
                    if asset:
                        category.image = asset
                        category.save(update_fields=['image'])
                count += 1
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'   ✓ {count} categorías migraron exitosamente'))
        return count
    
    def _migrate_subcategories(self, dry_run):
        """Migra imágenes de SubCategory."""
        count = 0
        subcategories = SubCategory.objects.filter(image__isnull=False).exclude(image='')
        self.stdout.write(f"   Encontrados {subcategories.count()} subcategorías con imágenes legacy")
        
        for subcat in subcategories:
            if self._create_or_get_image_asset(
                file_field=subcat.image,
                image_type=ImageType.SUBCATEGORY,
                name=subcat.subcategory_name,
                alt_text=f"Imagen de subcategoría: {subcat.subcategory_name}",
                dry_run=dry_run
            ):
                if not dry_run:
                    asset = self._get_existing_asset(subcat.image.name, ImageType.SUBCATEGORY)
                    if asset:
                        subcat.image_asset = asset
                        subcat.save(update_fields=['image_asset'])
                count += 1
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'   ✓ {count} subcategorías migraron exitosamente'))
        return count
    
    def _migrate_carousel(self, dry_run):
        """Migra imágenes de CarouselImage."""
        count = 0
        carousel_images = CarouselImage.objects.filter(image__isnull=False).exclude(image='')
        self.stdout.write(f"   Encontrados {carousel_images.count()} imágenes de carrusel con imágenes legacy")
        
        for carousel in carousel_images:
            if self._create_or_get_image_asset(
                file_field=carousel.image,
                image_type=ImageType.CAROUSEL,
                name=carousel.title,
                alt_text=carousel.description[:255] if carousel.description else '',
                dry_run=dry_run
            ):
                if not dry_run:
                    asset = self._get_existing_asset(carousel.image.name, ImageType.CAROUSEL)
                    if asset:
                        carousel.image_asset = asset
                        carousel.save(update_fields=['image_asset'])
                count += 1
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'   ✓ {count} imágenes de carrusel migraron exitosamente'))
        return count
    
    def _create_or_get_image_asset(self, file_field, image_type, name, alt_text, dry_run):
        """
        Crea o obtiene un ImageAsset existente.
        Retorna True si se creó o ya existe.
        Usa la ruta del archivo para verificar duplicados (idempotencia).
        """
        if not file_field or not file_field.name:
            return False
        
        # Verificar si ya existe un asset con esta ruta
        existing = ImageAsset.objects.filter(
            file=file_field.name,
            image_type=image_type
        ).first()
        
        if existing:
            return True  # Ya existe, no crear duplicado
        
        if dry_run:
            self.stdout.write(f"     [DRY-RUN] Crearía ImageAsset: {name} (tipo: {image_type})")
            return True
        
        # Crear nuevo asset
        try:
            asset = ImageAsset.objects.create(
                file=file_field,
                image_type=image_type,
                name=name[:255],
                alt_text=alt_text[:255] if alt_text else ''
            )
            self.stdout.write(f"     ✓ Creado ImageAsset ID {asset.id}: {name}")
            return True
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"     ⚠️  Error creando asset para {name}: {str(e)}"))
            return False
    
    def _get_existing_asset(self, file_name, image_type):
        """Obtiene el asset existente que corresponde a un archivo legacy."""
        return ImageAsset.objects.filter(
            file=file_name,
            image_type=image_type
        ).first()
    
    def _print_summary(self, stats, dry_run):
        """Imprime un resumen de la migración."""
        total = sum(stats.values())
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN DE MIGRACIÓN'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"  Products:        {stats['products']} 📦")
        self.stdout.write(f"  Gallery Items:   {stats['gallery']} 🖼️ ")
        self.stdout.write(f"  Categories:      {stats['categories']} 📂")
        self.stdout.write(f"  SubCategories:   {stats['subcategories']} 📂")
        self.stdout.write(f"  Carousel:        {stats['carousel']} 🎠")
        self.stdout.write(self.style.SUCCESS('-'*60))
        self.stdout.write(self.style.SUCCESS(f"  TOTAL:           {total} ✨"))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  Modo DRY-RUN: No se realizaron cambios.'))
            self.stdout.write(self.style.WARNING('    Ejecuta sin --dry-run para aplicar los cambios.\n'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Migración completada exitosamente.\n'))

import os
from django.core.management.base import BaseCommand
from store.models import Product, ProductGallery, CarouselImage
from store.utils import ImageProcessor, CarouselImageProcessor
from django.conf import settings

class Command(BaseCommand):
    help = 'Reprocesa todas las imágenes de productos y del carrusel usando el nuevo pipeline WebP single-size. Fase A: Lee de FK o legacy.'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Iniciando re-procesamiento de imágenes (Fase A)...")

        # 1. Productos
        products = Product.objects.exclude(images='').select_related('image')
        self.stdout.write(f"\n📦 Procesando {products.count()} imágenes principales de productos...")
        
        success = 0
        failed = 0
        skipped = 0
        for product in products:
            try:
                # Fase A: Intentar FK primero, fallback a legacy
                image_field = None
                if product.image and product.image.file and product.image.file.name:
                    image_field = product.image.file
                elif product.images:
                    image_field = product.images
                
                if not image_field:
                    skipped += 1
                    continue
                
                full_image_path = os.path.join(settings.MEDIA_ROOT, image_field.name)
                
                if os.path.exists(full_image_path):
                    processor = ImageProcessor(full_image_path)
                    if processor.process_image():
                        success += 1
                    else:
                        failed += 1
                        self.stderr.write(f"❌ Error procesando imagen para producto {product.code}")
                else:
                    self.stderr.write(f"⚠️  Imagen no encontrada en disco: {full_image_path}")
                    failed += 1
            except Exception as e:
                self.stderr.write(f"❌ Error con producto {product.code}: {e}")
                failed += 1
                
        self.stdout.write(self.style.SUCCESS(f"✅ Productos: {success} exitosos, {failed} fallidos, {skipped} omitidos"))

        # 2. Product Gallery
        gallery_images = ProductGallery.objects.exclude(image='').select_related('image_asset')
        self.stdout.write(f"\n🖼️  Procesando {gallery_images.count()} imágenes de galería...")
        
        success = 0
        failed = 0
        skipped = 0
        for g_img in gallery_images:
            try:
                # Fase A: Intentar FK primero, fallback a legacy
                image_field = None
                if g_img.image_asset and g_img.image_asset.file and g_img.image_asset.file.name:
                    image_field = g_img.image_asset.file
                elif g_img.image:
                    image_field = g_img.image
                
                if not image_field:
                    skipped += 1
                    continue
                
                full_image_path = os.path.join(settings.MEDIA_ROOT, image_field.name)
                if os.path.exists(full_image_path):
                    processor = ImageProcessor(full_image_path)
                    if processor.process_image():
                        success += 1
                    else:
                        failed += 1
                        self.stderr.write(f"❌ Error procesando imagen galería {g_img.id}")
                else:
                    self.stderr.write(f"⚠️  Imagen de galería no encontrada: {full_image_path}")
                    failed += 1
            except Exception as e:
                self.stderr.write(f"❌ Error con imagen de galería {g_img.id}: {e}")
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Galería: {success} exitosos, {failed} fallidos, {skipped} omitidos"))

        # 3. Carousel
        carousel_imgs = CarouselImage.objects.exclude(image='').select_related('image_asset')
        self.stdout.write(f"\n🎠 Procesando {carousel_imgs.count()} imágenes de carrusel...")
        
        success = 0
        failed = 0
        skipped = 0
        for c_img in carousel_imgs:
            try:
                # Fase A: Intentar FK primero, fallback a legacy
                image_field = None
                if c_img.image_asset and c_img.image_asset.file and c_img.image_asset.file.name:
                    image_field = c_img.image_asset.file
                elif c_img.image:
                    image_field = c_img.image
                
                if not image_field:
                    skipped += 1
                    continue
                
                full_image_path = os.path.join(settings.MEDIA_ROOT, image_field.name)
                if os.path.exists(full_image_path):
                    processor = CarouselImageProcessor(full_image_path)
                    if processor.process_image():
                        success += 1
                    else:
                        failed += 1
                        self.stderr.write(f"❌ Error procesando imagen carrusel {c_img.id}")
                else:
                    self.stderr.write(f"⚠️  Imagen carrusel no encontrada: {full_image_path}")
                    failed += 1
            except Exception as e:
                self.stderr.write(f"❌ Error con carrusel {c_img.id}: {e}")
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Carrusel: {success} exitosos, {failed} fallidos, {skipped} omitidos"))
        
        self.stdout.write(self.style.SUCCESS("\n✅ Re-procesamiento finalizado."))

import os
from PIL import Image
from django.conf import settings
from pathlib import Path

class ImageProcessor:
    SIZES = {
        'lg': (600, 600),
        'sm': (300, 300),
        'thumb': (150, 150)
    }
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.base_name = os.path.splitext(self.image_name)[0]
    
    def create_directories(self):
        """Crea la estructura de directorios si no existe"""
        base_dir = Path(settings.MEDIA_ROOT) / 'photos' / 'products'
        
        # Crear directorios para WebP
        webp_dirs = ['webp/lg', 'webp/sm', 'webp/thumb']
        for dir_path in webp_dirs:
            (base_dir / dir_path).mkdir(parents=True, exist_ok=True)
        
        # Crear directorios para originales y thumbnails
        (base_dir / 'original').mkdir(parents=True, exist_ok=True)
        (base_dir / 'thumbnails').mkdir(parents=True, exist_ok=True)
    
    def process_image(self):
        """Procesa la imagen en todos los formatos y tamaños necesarios"""
        self.create_directories()
        
        try:
            with Image.open(self.image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Guardar original
                original_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'original', self.image_name)
                img.save(original_path, quality=90)
                
                # Procesar diferentes tamaños en WebP
                for size_name, dimensions in self.SIZES.items():
                    # Redimensionar manteniendo proporción
                    resized_img = img.copy()
                    resized_img.thumbnail(dimensions, Image.Resampling.LANCZOS)
                    
                    # Guardar versión WebP
                    webp_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'webp', size_name, f"{self.base_name}.webp")
                    resized_img.save(webp_path, 'WEBP', quality=85)
                    
                    # Para thumbnails, guardar también en formato original
                    if size_name == 'thumb':
                        thumb_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'thumbnails', self.image_name)
                        resized_img.save(thumb_path, quality=85)
                
                return True
                
        except Exception as e:
            print(f"Error procesando imagen {self.image_name}: {str(e)}")
            return False

    @staticmethod
    def get_image_urls(base_name, extension):
        """Obtiene las URLs para todas las versiones de una imagen"""
        return {
            'original': f'photos/products/original/{base_name}{extension}',
            'webp': {
                'lg': f'photos/products/webp/lg/{base_name}.webp',
                'sm': f'photos/products/webp/sm/{base_name}.webp',
                'thumb': f'photos/products/webp/thumb/{base_name}.webp'
            },
            'thumbnail': f'photos/products/thumbnails/{base_name}{extension}'
        } 
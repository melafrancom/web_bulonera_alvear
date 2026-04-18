import os
from PIL import Image
from django.conf import settings
from pathlib import Path

class ImageProcessor:
    MAX_SIZE = (1200, 1200)
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.base_name = os.path.splitext(self.image_name)[0]
    
    def create_directories(self):
        """Crea la estructura de directorios si no existe"""
        base_dir = Path(settings.MEDIA_ROOT) / 'photos' / 'products'
        
        # Crear directorios para WebP y originales
        (base_dir / 'webp').mkdir(parents=True, exist_ok=True)
        (base_dir / 'original').mkdir(parents=True, exist_ok=True)
    
    def process_image(self):
        """Procesa la imagen en WebP responsivo"""
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
                
                # Guardar original solo si la ruta es distinta (ej. no viene desde el media_bank ya ruteada)
                original_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'original', self.image_name)
                if os.path.abspath(self.image_path) != os.path.abspath(original_path):
                    img.save(original_path, quality=90)
                
                # Redimensionar manteniendo proporción (max 1200x1200px para que cubra bien productos con lupa/zoom o pantallas retina)
                resized_img = img.copy()
                resized_img.thumbnail(self.MAX_SIZE, Image.Resampling.LANCZOS)
                
                # Guardar versión WebP
                webp_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'products', 'webp', f"{self.base_name}.webp")
                resized_img.save(webp_path, 'WEBP', quality=82)
                
                return True
                
        except Exception as e:
            print(f"Error procesando imagen {self.image_name}: {str(e)}")
            return False

    @staticmethod
    def get_image_urls(base_name, extension):
        """Obtiene URLs de imagen con fallback a subcarpeta lg/ para WebP.
        
        En producción con OLS, los WebP en la raíz de webp/ devuelven 404,
        pero funcionan en webp/lg/. Este método busca el archivo en disco
        y devuelve la ruta que existe.
        """
        # Buscar WebP con fallback: raíz → lg/
        webp_relative = f'photos/products/webp/{base_name}.webp'
        for subdir in ['', 'lg/']:
            candidate = os.path.join(
                settings.MEDIA_ROOT,
                'photos', 'products', 'webp', subdir,
                f'{base_name}.webp'
            )
            if os.path.isfile(candidate):
                webp_relative = f'photos/products/webp/{subdir}{base_name}.webp'
                break
        
        return {
            'original': f'photos/products/original/{base_name}{extension}',
            'webp': webp_relative
        } 

class CarouselImageProcessor:
    MAX_WIDTH = 1920
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.base_name = os.path.splitext(self.image_name)[0]
    
    def create_directories(self):
        """Crea la estructura de directorios si no existe"""
        base_dir = Path(settings.MEDIA_ROOT) / 'photos' / 'carousel'
        
        # Crear directorio principal para WebP
        (base_dir / 'webp').mkdir(parents=True, exist_ok=True)
    
    def process_image(self):
        """Procesa la imagen a una sola versión WebP para el carrusel"""
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
                
                # Redimensionar el max_width a 1920 px (mantiene proporción nativa de la imagen sin recortar el centro)
                # El "aspect ratio" del carrusel se manejará por CSS (object-fit: cover en height: 390px/responsivo)
                if img.width > self.MAX_WIDTH:
                    new_height = int((self.MAX_WIDTH / img.width) * img.height)
                    img = img.resize((self.MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
                
                # Guardar versión WebP
                webp_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'carousel', 'webp', f"{self.base_name}.webp")
                img.save(webp_path, 'WEBP', quality=82)
                
                return True
                
        except Exception as e:
            print(f"Error procesando imagen del carrusel {self.image_name}: {str(e)}")
            return False

    @staticmethod
    def get_image_urls(base_name):
        """Obtiene la URL de la imagen del carrusel en WebP"""
        return {
            'webp': f'photos/carousel/webp/{base_name}.webp'
        }


class BannerImageProcessor:
    """Procesador para banners de la Home (banner_landing, banner_double, banner_triple)."""
    MAX_WIDTH = 1920
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.base_name = os.path.splitext(self.image_name)[0]
    
    def create_directories(self):
        """Crea la estructura de directorios si no existe"""
        base_dir = Path(settings.MEDIA_ROOT) / 'photos' / 'banners'
        (base_dir / 'webp').mkdir(parents=True, exist_ok=True)
    
    def process_image(self):
        """Procesa la imagen a WebP para banners (1920px max width)"""
        self.create_directories()
        
        try:
            with Image.open(self.image_path) as img:
                # Convertir a RGB si es necesario (maneja RGBA/LA con fondo blanco)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Redimensionar preservando aspect ratio (1920px de ancho máximo)
                if img.width > self.MAX_WIDTH:
                    new_height = int((self.MAX_WIDTH / img.width) * img.height)
                    img = img.resize((self.MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
                
                # Guardar versión WebP
                webp_path = os.path.join(settings.MEDIA_ROOT, 'photos', 'banners', 'webp', f"{self.base_name}.webp")
                img.save(webp_path, 'WEBP', quality=82)
                
                return True
                
        except Exception as e:
            print(f"Error procesando banner {self.image_name}: {str(e)}")
            return False

    @staticmethod
    def get_image_urls(base_name):
        """Obtiene la URL de la imagen del banner en WebP"""
        return {
            'webp': f'photos/banners/webp/{base_name}.webp'
        }


class CategoryImageProcessor:
    """Procesador para imágenes de categorías y subcategorías (cuadradas 400x400)."""
    MAX_SIZE = (400, 400)
    
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.base_name = os.path.splitext(self.image_name)[0]
    
    def create_directories(self, is_subcategory=False):
        """Crea la estructura de directorios si no existe"""
        base_dir = Path(settings.MEDIA_ROOT) / 'photos' / 'categories'
        (base_dir / 'webp').mkdir(parents=True, exist_ok=True)
        if is_subcategory:
            (base_dir / 'subcategories' / 'webp').mkdir(parents=True, exist_ok=True)
    
    def process_image(self, is_subcategory=False):
        """Procesa la imagen a WebP para categorías (400x400 cuadrado con thumbnail)"""
        self.create_directories(is_subcategory=is_subcategory)
        
        try:
            with Image.open(self.image_path) as img:
                # Convertir a RGB si es necesario (maneja RGBA/LA con fondo blanco)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Thumbnail mantiene el aspect ratio dentro de 400x400
                img.thumbnail(self.MAX_SIZE, Image.Resampling.LANCZOS)
                
                # Guardar versión WebP
                subdir = 'subcategories/webp' if is_subcategory else 'webp'
                webp_path = os.path.join(
                    settings.MEDIA_ROOT, 'photos', 'categories', subdir,
                    f"{self.base_name}.webp"
                )
                img.save(webp_path, 'WEBP', quality=85)
                
                return True
                
        except Exception as e:
            print(f"Error procesando categoría {self.image_name}: {str(e)}")
            return False

    @staticmethod
    def get_image_urls(base_name, is_subcategory=False):
        """Obtiene la URL de la imagen de categoría en WebP"""
        subdir = 'subcategories/webp' if is_subcategory else 'webp'
        return {
            'webp': f'photos/categories/{subdir}/{base_name}.webp'
        }


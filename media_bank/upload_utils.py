import os
import unidecode
from django.conf import settings

def overwrite_upload_path(relative_path):
    """
    Elimina el archivo existente (si lo hay) en la ruta relativa especificada 
    para evitar que el FileSystemStorage de Django agregue sufijos aleatorios.
    """
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    if os.path.isfile(full_path):
        os.remove(full_path)
    return relative_path

def create_clean_filename(filename):
    """
    Limpia el nombre del archivo para eliminar caracteres problemáticos.
    (Acentos a sin acento, espacios a guiones)
    """
    name, ext = os.path.splitext(filename)
    clean_name = unidecode.unidecode(name).replace(' ', '-')
    return f"{clean_name}{ext}"

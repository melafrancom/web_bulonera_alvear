"""
Utilidades de gestión y sanitización de archivos de subida para media_bank.

Provee funciones para confinamiento de rutas contra Path Traversal,
sanitización de nombres de archivo y validación estricta de imágenes (magic bytes y extensiones).
"""
import os
from pathlib import Path
import unidecode
from PIL import Image

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError


# REGLA: Extensiones permitidas exclusivamente para activos de imagen
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# CUIDADO: Límite de tamaño en memoria/disco para evitar DoS por descompresión de archivos desmedidos
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def overwrite_upload_path(relative_path: str) -> str:
    """
    Confina y elimina el archivo existente en la ruta relativa para evitar sufijos aleatorios.

    QUÉ:
        Resuelve la ruta completa del archivo asegurando que resida dentro de MEDIA_ROOT.
        Si el archivo ya existe físicamente, lo elimina. Retorna la ruta relativa sanitizada.

    POR QUÉ:
        Previene la vulnerabilidad de Path Traversal (CWE-22 / AUD-MB-001) donde un nombre
        malicioso como '../../etc/cron' o '../../manage.py' podría manipular o eliminar
        archivos arbitrarios fuera del directorio multimedia del servidor.

    CÓMO:
        1. Normaliza separadores unificando barras invertidas a '/'.
        2. Bloquea rutas absolutas que intenten saltar la raíz de medios.
        3. Resuelve la ruta canónica absoluta con Path.resolve().
        4. Verifica el confinamiento con relative_to(media_root) levantando SuspiciousFileOperation ante escape.
        5. Si el archivo existe físicamente en el sistema de archivos, lo elimina de forma segura.
    """
    if not relative_path:
        raise SuspiciousFileOperation("Ruta relativa vacía.")

    # REGLA: Unificar separadores antes de resolver para portabilidad Windows/Linux
    normalized_path = relative_path.replace('\\', '/')

    # REGLA: Rechazar rutas absolutas explícitas (ej: /etc/shadow, C:/boot.ini)
    if os.path.isabs(normalized_path) or normalized_path.startswith('/'):
        raise SuspiciousFileOperation(
            f"Acceso denegado: la ruta '{relative_path}' es absoluta o intenta escapar de MEDIA_ROOT."
        )

    media_root = Path(settings.MEDIA_ROOT).resolve()
    target_path = (media_root / normalized_path).resolve()

    # REGLA: Confinamiento estricto al árbol de MEDIA_ROOT
    try:
        relative_resolved = target_path.relative_to(media_root)
    except ValueError:
        # CUIDADO: Intento de evasión de directorio detectado
        raise SuspiciousFileOperation(
            f"Acceso denegado: la ruta '{relative_path}' intenta escapar de MEDIA_ROOT."
        )

    # Si el archivo ya existe, eliminarlo para permitir sobreescritura limpia
    if target_path.is_file():
        try:
            target_path.unlink()
        except OSError:
            # POR QUÉ: No interrumpir la subida si el archivo está bloqueado temporalmente
            pass

    return str(relative_resolved).replace('\\', '/')


def create_clean_filename(filename: str) -> str:
    """
    Limpia y sanitiza el nombre del archivo para almacenamiento seguro.

    QUÉ:
        Translitera acentos, sustituye espacios por guiones y normaliza la extensión a minúsculas.

    POR QUÉ:
        Evita problemas de codificación de caracteres en sistemas de archivos Linux/Windows,
        espacios en URLs públicas y extensiones en mayúsculas inconsistentes (.JPG vs .jpg).

    CÓMO:
        1. Separa el nombre base y la extensión.
        2. Translitera caracteres especiales a ASCII con unidecode.
        3. Reemplaza espacios y caracteres conflictivos por guiones.
        4. Convierte la extensión a minúsculas.
    """
    name, ext = os.path.splitext(filename)
    clean_name = unidecode.unidecode(name).replace(' ', '-').strip('-')
    # Sanitizar caracteres no seguros dejando solo alfanuméricos, guiones y guiones bajos
    clean_name = "".join(c for c in clean_name if c.isalnum() or c in ('-', '_'))
    if not clean_name:
        clean_name = 'asset'
    clean_ext = ext.lower()
    return f"{clean_name}{clean_ext}"


def validate_image_file(file) -> None:
    """
    Validador estricto para ImageField en modelos y formularios.

    QUÉ:
        Verifica tamaño máximo, extensión permitida y cabecera real de imagen (magic bytes).

    POR QUÉ:
        Previene subida de ejecutables camuflados (ej: shell.php.jpg) o bombas de descompresión
        que colapsen la memoria del servidor o expongan Remote Code Execution.

    CÓMO:
        1. Valida el tamaño en bytes del archivo.
        2. Valida que la extensión esté en la lista blanca ALLOWED_IMAGE_EXTENSIONS.
        3. Abre el flujo binario con Pillow y ejecuta verify() para validar estructura interna.
        4. Rebobina el puntero del archivo a la posición inicial (seek(0)).
    """
    # 1. Validación de tamaño
    if hasattr(file, 'size') and file.size is not None and file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            f"El archivo excede el tamaño máximo permitido de {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # 2. Validación de extensión
    filename = getattr(file, 'name', '') or ''
    ext = os.path.splitext(filename)[1].lower() if filename else ''
    if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Extensión no permitida '{ext}'. Tipos aceptados: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    # 3. Validación de contenido real con Pillow (Magic Bytes / Structural Verification)
    try:
        current_pos = file.tell() if hasattr(file, 'tell') else 0
        img = Image.open(file)
        img.verify()

        ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
        if img.format not in ALLOWED_FORMATS:
            raise ValidationError(f"Formato de imagen '{img.format}' no soportado.")
    except Exception as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError("El archivo no es una imagen válida o está dañado.")
    finally:
        # REGLA: Rebobinar siempre el stream para que Django pueda leerlo y guardarlo posteriormente
        if hasattr(file, 'seek'):
            file.seek(current_pos if 'current_pos' in locals() else 0)

"""
Script de Verificación Sanitizada de Aislamiento (Gate 0).
Comprueba exhaustivamente el estado de configuración de staging SIN imprimir contraseñas ni tokens sensibles.
Falla explícitamente (exit 1) si cualquier parámetro de aislamiento, base de datos o seguridad no cumple.
"""
import os
import sys

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.staging')

try:
    import django
    django.setup()
    from django.conf import settings
except Exception as e:
    print(f"Error cargando Django: {e}")
    sys.exit(1)

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("VERIFICACIÓN SANITIZADA DE AISLAMIENTO (GATE 0)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

checks = []

# 1. Verificación de Módulo de Configuración
settings_mod = getattr(settings, 'SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', ''))
is_staging_mod = (settings_mod == 'web_bulonera.settings.staging')
checks.append(("SETTINGS_MODULE == staging", is_staging_mod, f"Actual: {settings_mod}"))

# 2. Verificación estricta de DEBUG=False
is_debug_false = (settings.DEBUG is False)
checks.append(("DEBUG == False (Modo Producción Local)", is_debug_false, f"Actual: {settings.DEBUG}"))

# 3. Verificación de Base de Datos Local en Settings
db_name = settings.DATABASES.get('default', {}).get('NAME', '')
db_host = settings.DATABASES.get('default', {}).get('HOST', '')
is_db_local_name = (db_name == 'buloneraalvearDB_dev')
is_db_local_host = (db_host == 'db_mariadb')
checks.append(("DB_NAME en Settings == buloneraalvearDB_dev", is_db_local_name, f"Actual: {db_name}"))
checks.append(("DB_HOST en Settings == db_mariadb", is_db_local_host, f"Actual: {db_host}"))

# 4. Verificación de Conexión Real y Activa a MariaDB (Live DB Query)
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE();")
        active_db = cursor.fetchone()[0]
    is_live_db_ok = (active_db == 'buloneraalvearDB_dev')
    checks.append(("Conexión Activa a DB (SELECT DATABASE())", is_live_db_ok, f"Conectado a: {active_db}"))
except Exception as e:
    checks.append(("Conexión Activa a DB (SELECT DATABASE())", False, f"Error SQL: {e}"))

# 5. Verificación de Email en Memoria
is_email_locmem = ('locmem' in settings.EMAIL_BACKEND)
checks.append(("EMAIL_BACKEND en memoria (locmem)", is_email_locmem, f"Actual: {settings.EMAIL_BACKEND}"))

# 6. Verificación de Celery Eager Mode
is_celery_eager = bool(getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False))
checks.append(("CELERY_TASK_ALWAYS_EAGER == True", is_celery_eager, f"Actual: {is_celery_eager}"))

# 7. Verificación de Tokens y Credenciales Externas (Deben estar estrictamente vacíos)
external_keys = [
    'META_CAPI_TOKEN',
    'META_PIXEL_ID',
    'INDEXNOW_API_KEY',
    'GOOGLE_MAPS_EMBED_KEY',
    'GOOGLE_PLACE_ID',
]

for key in external_keys:
    val = getattr(settings, key, '')
    is_empty = (not val)
    checks.append((f"{key} vacío", is_empty, "EMPTY" if is_empty else "CONFIGURED (PELIGRO: Token presente)"))

print("\nPARÁMETROS CRÍTICOS DE AISLAMIENTO:")
all_passed = True
for name, passed, detail in checks:
    status_icon = "✅ OK   " if passed else "❌ FALLO"
    print(f"  [{status_icon}] {name:<42} -> {detail}")
    if not passed:
        all_passed = False

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
if all_passed:
    print("✅ ESTADO: AISLAMIENTO TOTAL VALIDADO Y CONFIRMADO. SEGURO PARA CARGA.")
    sys.exit(0)
else:
    print("❌ ESTADO: FALLA EN LAS CONDICIONES DE AISLAMIENTO. ABORTANDO GATE 1.")
    sys.exit(1)

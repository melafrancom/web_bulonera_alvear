# Script de Reimportación de Productos
# Proyecto: Bulonera Alvear
# Fecha: 2026-04-20

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  REIMPORTACIÓN DE PRODUCTOS" -ForegroundColor Cyan
Write-Host "  Bulonera Alvear - Fix Bug Importación" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "Error: Este script debe ejecutarse desde el directorio raíz del proyecto" -ForegroundColor Red
    exit 1
}

# Paso 1: Verificar estado actual
Write-Host "[1/5] Verificando estado actual del catálogo..." -ForegroundColor Yellow
$pythonScript = @"
from store.models import Product
total = Product.objects.count()
corruptos = Product.objects.filter(code__endswith='.0').count()
print(f'Total productos: {total}')
print(f'Productos con .0: {corruptos}')
"@

$pythonScript | docker-compose exec -T bulonera_web python manage.py shell

Write-Host ""
$continue = Read-Host "¿Desea continuar con la reimportación? (s/n)"
if ($continue -ne "s" -and $continue -ne "S") {
    Write-Host "Operación cancelada" -ForegroundColor Red
    exit 0
}

# Paso 2: Backup de la base de datos
Write-Host ""
Write-Host "[2/5] Creando backup de la base de datos..." -ForegroundColor Yellow
$backupFile = "backup_pre_reimport_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
docker-compose exec -T db_mariadb mysqldump -u root -proot bulonera_web | Out-File -FilePath $backupFile -Encoding utf8
Write-Host "✓ Backup creado: $backupFile" -ForegroundColor Green

# Paso 3: Eliminar productos corruptos
Write-Host ""
Write-Host "[3/5] Eliminando productos con sufijo .0..." -ForegroundColor Yellow
$deleteScript = @"
from store.models import Product
corruptos = Product.objects.filter(code__endswith='.0')
count = corruptos.count()
corruptos.delete()
print(f'✓ Eliminados {count} productos corruptos')
"@

$deleteScript | docker-compose exec -T bulonera_web python manage.py shell

# Paso 4: Instrucciones para reimportación manual
Write-Host ""
Write-Host "[4/5] Reimportación de productos" -ForegroundColor Yellow
Write-Host ""
Write-Host "Por favor, siga estos pasos para reimportar los productos:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Abra el panel Admin en su navegador:"
Write-Host "   http://localhost:8002/admin/store/product/import-products/" -ForegroundColor White
Write-Host ""
Write-Host "2. Seleccione el archivo Excel a importar:"
Write-Host "   - Arandelas.xlsx (para arandelas)" -ForegroundColor White
Write-Host "   - 2 lista completa para web.xlsx (para catálogo completo)" -ForegroundColor White
Write-Host ""
Write-Host "3. Haga clic en 'Importar'"
Write-Host ""
Write-Host "4. Verifique que no haya errores en el resultado"
Write-Host ""
Read-Host "Presione ENTER cuando haya completado la importación"

# Paso 5: Verificar resultado
Write-Host ""
Write-Host "[5/5] Verificando resultado de la reimportación..." -ForegroundColor Yellow
$verifyScript = @"
from store.models import Product
total = Product.objects.count()
corruptos = Product.objects.filter(code__endswith='.0').count()
print('')
print('========================================')
print('  RESULTADO DE LA REIMPORTACIÓN')
print('========================================')
print(f'Total productos: {total}')
print(f'Productos con .0: {corruptos}')
print('')
if corruptos == 0:
    print('✓ ¡ÉXITO! No hay productos corruptos')
else:
    print(f'⚠ ADVERTENCIA: Aún hay {corruptos} productos con .0')
    print('  Verifique que la importación se haya realizado correctamente')
print('========================================')
"@

$verifyScript | docker-compose exec -T bulonera_web python manage.py shell

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  PROCESO COMPLETADO" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backup guardado en: $backupFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "Si algo salió mal, puede restaurar el backup con:"
Write-Host "Get-Content $backupFile | docker-compose exec -T db_mariadb mysql -u root -proot bulonera_web" -ForegroundColor Yellow

# 🏋️ Suite de Pruebas de Carga (Load Testing) — BULONERA WEB

Suite contenerizada de pruebas de carga basada en **Locust 2.32.8** para evaluar la capacidad y resistencia del backend Django + uWSGI + Redis + MariaDB bajo condiciones de tráfico concurrente.

---

## 📋 Estructura de la Suite

- `locustfile.py`: Define los perfiles de usuario divididos por fases:
  - **`CatalogUser` (Fase A1):** Navegación de catálogo (Home, Categorías, Detalle de producto, Blog). *Nota:* El detalle de producto genera una sesión anónima inicial en `django_session` al invocar `_cart_id`.
  - **`SearchUser` (Fase A2):** Búsquedas por término clave (mide el impacto de inserciones en `ProductSearch`).
  - **`CartUser` (Fase B):** Agregado y visualización de productos en el carrito (gestión de CSRF y sesiones).
- `test_data.json`: Fixtures parametrizadas (categorías, subcategorías, slugs de productos y palabras clave reales).
- `monitor.py`: Script de telemetría continua para capturar picos de hilos de MariaDB y deltas de caché/queries por escalón.
- `results/`: Directorio donde se exportan los reportes CSV y gráficos (montado como volumen).

---

## 🚦 Gate 0: Verificación Previa Obligatoria (Aislamiento Sanitizado)

Antes de iniciar cualquier prueba, validar que el entorno de staging esté estrictamente aislado. El script `check_isolation.py` valida que `DEBUG=False`, que la base de datos apunte y se conecte a `buloneraalvearDB_dev` en `db_mariadb`, que Celery esté en modo eager y que todas las credenciales externas estén estrictamente vacías (abortando con código de salida `1` ante cualquier fallo, sin exponer contraseñas ni tokens en terminal):

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec bulonera_web python /app/tests/load/check_isolation.py
```

---

## 🚀 Cómo Ejecutar la Suite

> [!WARNING]
> **Convivencia con Entorno de Desarrollo:**
> Staging comparte los volúmenes de datos (`mariadb_data`, `redis_data`) con la base local. Detener con `down` apagará los servicios de base de datos.
> Consulta la sección [Detención y Restauración](#-detención-y-restauración) para saber cómo pausar Locust o restaurar el servidor de desarrollo sin perder datos.

### 1. Iniciar el Entorno de Staging
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

### 2. Acceder al Dashboard Web de Locust
Abre tu navegador en:
👉 **[http://localhost:8089](http://localhost:8089)**

- **Number of users (peak concurrency):** 10 (Baseline) → 100 (Normal) → 500 (Elevada) → 1,000 (Límite).
- **Ramp up (users started/sec):** 2 / 5 / 10 / 20.
- **Host:** `http://bulonera-web:8002` (configurado por defecto con alias RFC 1034/1035).
- **Select user class:** Elegir `CatalogUser` (A1), `SearchUser` (A2) o `CartUser` (B).

---

## 📊 Monitoreo de Telemetría Continuo (Picos y Deltas)

Durante la ejecución de cada escalón, iniciar el monitor en una terminal paralela para capturar valores pico y deltas exactos:

### 1. Monitor Continuo Automatizado (Recomendado)
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec bulonera_web python /app/tests/load/monitor.py --duration 180 --interval 2
```
*Genera en tiempo real:*
- Máximo de `Threads_connected` y `Threads_running`.
- $\Delta \text{Slow\_queries}$ generadas durante el escalón.
- $\Delta \text{keyspace\_hits}$ y $\Delta \text{keyspace\_misses}$ con el Hit Ratio % exacto.
- Si Redis o MariaDB sufren una caída, el monitor marca la ejecución como **fallida** (`exit 1`) y no computa deltas engañosos.

### 2. Monitoreo de Recursos en Contenedores
```bash
docker stats
```
*(Dejar corriendo sin `--no-stream` para observar picos de CPU y RAM en tiempo real).*

---

## 🛑 Detención y Restauración

Para gestionar el ciclo de vida de los servicios sin afectar el trabajo de desarrollo habitual, utiliza los comandos apropiados:

### A. Pausar únicamente Locust (mantener uWSGI de staging activo)
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml stop locust
```

### B. Salir de Staging y Restaurar el Servidor Web de Desarrollo
Detiene Locust y vuelve a arrancar el contenedor web con el `runserver` de desarrollo estándar (autoreload, DEBUG local):
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml stop locust
docker compose -f docker-compose.yml up -d bulonera_web
```

### C. Apagar todo el stack (¡Cuidado: detiene también MariaDB y Redis!)
Conserva los datos montados en volúmenes Docker, pero apaga todos los contenedores:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml down
```

---

## 📐 Interpretación Técnica y Limitaciones Metodológicas

1. **Muestreo Discreto (2 segundos):** El monitor registra picos observados en muestras discretas cada 2 segundos. Esto permite detectar saturaciones sostenidas, pero no garantiza capturar micro-picos transitorios de duración inferior a ese intervalo.
2. **Alcance de Estadísticas en Redis:** Las métricas de `INFO stats` (`keyspace_hits`, `keyspace_misses`, `evicted_keys`) son globales a toda la instancia de Redis (no aisladas a la DB 2). En entornos donde Redis conviva con tráfico concurrente de desarrollo, los deltas pueden verse afectados.
3. **Código de Aplicación (`cart/context_processors.py`):** Contiene una guarda defensiva (`hasattr(request, 'session')` y `getattr(request, 'user', None)`) que evita errores de atributo en vistas tempranas de excepción (404/500/CSRF) durante pruebas de carga o fallos de middleware. Está validada mediante 47 tests unitarios de la suite de carrito.
4. **CPU del Contenedor Web:** Staging se ejecuta en la máquina de desarrollo (múltiples cores disponibles), a diferencia del VPS de producción (2 vCPUs). En `docker stats`, 100% equivale a 1 core saturado. Expresar el consumo siempre relativo a la cantidad de núcleos disponibles.
5. **Conexiones MariaDB:** uWSGI staging opera con 6 slots (3 procesos x 2 hilos) y `CONN_MAX_AGE = 0`. El valor base inicial de `Threads_connected` suele ser de 1-2. Un pico mayor a 20-30 debe tratarse como señal de alerta para investigar bloqueo de tablas o retención por queries lentas.

"""
Monitor de Telemetría Continuo para Pruebas de Carga en Staging.
Muestrea periódicamente (cada 2s) MariaDB y Redis, capturando picos observados y deltas.

LIMITACIONES METODOLÓGICAS:
1. Muestreo Discreto: Muestrea cada N segundos; captura el máximo observado en las muestras,
   no garantiza registrar micro-picos sub-segundo.
2. Alcance de Redis: Las métricas de 'INFO stats' son globales a la instancia de Redis
   (servidor completo), no aisladas a la DB 2. Cualquier tráfico concurrente en la instancia
   se refleja en los contadores.

Uso dentro del contenedor bulonera_web:
    python /app/tests/load/monitor.py [--duration SEGUNDOS] [--interval SEGUNDOS]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.staging')

try:
    import django
    django.setup()
    from django.db import connection
    import django_redis
except Exception as e:
    print(f"❌ Error fatal inicializando Django para monitor: {e}")
    sys.exit(1)


def get_mariadb_status():
    """Obtiene variables de estado clave de MariaDB. Lanza excepción si falla."""
    with connection.cursor() as cursor:
        cursor.execute("SHOW STATUS WHERE Variable_name IN ('Threads_connected', 'Threads_running', 'Slow_queries');")
        rows = cursor.fetchall()
        return {row[0]: int(row[1]) for row in rows}


def get_redis_stats():
    """
    Obtiene estadísticas globales de Redis.
    Lanza excepción si Redis no responde para evitar ocultar fallos.
    """
    redis_client = django_redis.get_redis_connection("default")
    info = redis_client.info("stats")
    return {
        "keyspace_hits": int(info.get("keyspace_hits", 0)),
        "keyspace_misses": int(info.get("keyspace_misses", 0)),
        "evicted_keys": int(info.get("evicted_keys", 0)),
    }


def main():
    parser = argparse.ArgumentParser(description="Monitor de Telemetría Continuo")
    parser.add_argument("--duration", type=int, default=0, help="Duración en segundos (0 para infinito hasta Ctrl+C)")
    parser.add_argument("--interval", type=int, default=2, help="Intervalo de muestreo en segundos")
    args = parser.parse_args()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Iniciando muestreo continuo de infraestructura (MariaDB + Redis)...")
    print(f"Intervalo: {args.interval}s | Duración: {'Indefinida (Ctrl+C para finalizar)' if args.duration == 0 else f'{args.duration}s'}")
    print("Nota: Picos corresponden a muestras discretas; contadores Redis son globales de la instancia.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # Validación inicial estricta: abortar si los servicios no responden al inicio
    try:
        initial_db = get_mariadb_status()
    except Exception as e:
        print(f"❌ ERROR FATAL: No se puede conectar a MariaDB para telemetría: {e}")
        sys.exit(1)

    try:
        initial_redis = get_redis_stats()
    except Exception as e:
        print(f"❌ ERROR FATAL: No se puede conectar a Redis para telemetría: {e}")
        sys.exit(1)

    peak_threads_connected = initial_db.get("Threads_connected", 0)
    peak_threads_running = initial_db.get("Threads_running", 0)
    redis_errors = []
    mariadb_errors = []

    last_valid_redis = initial_redis
    last_valid_db = initial_db

    start_time = time.time()
    sample_count = 0

    try:
        while True:
            sample_count += 1
            elapsed = int(time.time() - start_time)

            # Muestreo MariaDB
            try:
                curr_db = get_mariadb_status()
                last_valid_db = curr_db
                tc = curr_db.get("Threads_connected", 0)
                tr = curr_db.get("Threads_running", 0)
                if tc > peak_threads_connected:
                    peak_threads_connected = tc
                if tr > peak_threads_running:
                    peak_threads_running = tr
                delta_slow = curr_db.get("Slow_queries", 0) - initial_db.get("Slow_queries", 0)
                db_status_str = f"DB Threads: {tc} (pico: {peak_threads_connected}) | Running: {tr} (pico: {peak_threads_running}) | Δ Slow: {delta_slow}"
            except Exception as e:
                mariadb_errors.append((elapsed, str(e)))
                db_status_str = f"DB: ❌ FALLO [{e}]"

            # Muestreo Redis
            try:
                curr_redis = get_redis_stats()
                last_valid_redis = curr_redis
                delta_hits = curr_redis.get("keyspace_hits", 0) - initial_redis.get("keyspace_hits", 0)
                delta_misses = curr_redis.get("keyspace_misses", 0) - initial_redis.get("keyspace_misses", 0)
                total_cache_ops = delta_hits + delta_misses
                hit_ratio = (delta_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0.0
                redis_status_str = f"Redis Hits/Misses: {delta_hits}/{delta_misses} (Hit Ratio: {hit_ratio:.1f}%)"
            except Exception as e:
                redis_errors.append((elapsed, str(e)))
                redis_status_str = f"Redis: ❌ FALLO [{e}]"

            sys.stdout.write(f"\r[{elapsed:03d}s] {db_status_str} | {redis_status_str}")
            sys.stdout.flush()

            if args.duration > 0 and elapsed >= args.duration:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nMuestreo interrumpido por el usuario.")

    final_elapsed = int(time.time() - start_time)
    
    # Procesamiento MariaDB
    if mariadb_errors:
        db_delta_slow_str = f"NO DISPONIBLE ({len(mariadb_errors)} fallos registrados)"
    else:
        db_delta_slow_str = str(last_valid_db.get("Slow_queries", 0) - initial_db.get("Slow_queries", 0))

    # Procesamiento Redis: No ocultar fallos ni inventar deltas o 0% si Redis falló
    if redis_errors:
        redis_delta_hits_str = f"NO DISPONIBLE ({len(redis_errors)} fallos)"
        redis_delta_misses_str = f"NO DISPONIBLE ({len(redis_errors)} fallos)"
        redis_hit_ratio_str = f"NO DISPONIBLE (Fallo de comunicación con Redis)"
        redis_evictions_str = f"NO DISPONIBLE ({len(redis_errors)} fallos)"
    else:
        delta_hits = last_valid_redis.get("keyspace_hits", 0) - initial_redis.get("keyspace_hits", 0)
        delta_misses = last_valid_redis.get("keyspace_misses", 0) - initial_redis.get("keyspace_misses", 0)
        delta_evictions = last_valid_redis.get("evicted_keys", 0) - initial_redis.get("evicted_keys", 0)
        total_cache_ops = delta_hits + delta_misses
        hit_ratio = (delta_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0.0
        redis_delta_hits_str = f"{delta_hits} (global instancia)"
        redis_delta_misses_str = f"{delta_misses} (global instancia)"
        redis_hit_ratio_str = f"{hit_ratio:.2f}%"
        redis_evictions_str = f"{delta_evictions} (global instancia)"

    print("\n\n" + "═" * 60)
    print("📊 RESUMEN CONSOLIDADO DE TELEMETRÍA")
    print("═" * 60)
    print(f"Duración de la prueba:            {final_elapsed} segundos ({sample_count} muestras de {args.interval}s)")
    print(f"MariaDB Threads_connected (base): {initial_db.get('Threads_connected', 0)}")
    print(f"MariaDB Threads_connected (pico): {peak_threads_connected}")
    print(f"MariaDB Threads_running (pico):   {peak_threads_running}")
    print(f"MariaDB Δ Slow_queries:           {db_delta_slow_str}")
    print(f"Redis Δ keyspace_hits:            {redis_delta_hits_str}")
    print(f"Redis Δ keyspace_misses:          {redis_delta_misses_str}")
    print(f"Redis Hit Ratio estimado:         {redis_hit_ratio_str}")
    print(f"Redis Δ evicted_keys:             {redis_evictions_str}")
    print("─" * 60)
    print("⚠️ ACLARACIONES METODOLÓGICAS:")
    print(f"1. Muestreo Discreto ({args.interval}s): Los picos reflejan el máximo observado")
    print("   en las muestras tomadas; no garantizan capturar picos transitorios sub-segundo.")
    print("2. Alcance Global Redis: Las estadísticas de 'INFO stats' son globales a la")
    print("   instancia Redis completa (no aisladas a DB 2). Tráfico concurrente en el host")
    print("   puede contaminar los deltas reportados.")
    print("═" * 60)

    if redis_errors or mariadb_errors:
        print("\n❌ ESTADO FINAL: TELEMETRÍA FALLIDA POR ERRORES DE INFRAESTRUCTURA.")
        if mariadb_errors:
            print(f"  - Fallos de lectura en MariaDB: {len(mariadb_errors)} veces.")
        if redis_errors:
            print(f"  - Fallos de lectura en Redis:   {len(redis_errors)} veces.")
        print("  RESULTADO: La prueba debe considerarse INVALIDADA hasta estabilizar la infraestructura.")
        sys.exit(1)
    else:
        print("\n✅ Muestreo de telemetría completado exitosamente sin pérdidas de conexión.")
        sys.exit(0)


if __name__ == "__main__":
    main()

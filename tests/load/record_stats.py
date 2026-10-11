"""
Monitor de Recursos de Contenedores en Vivo (Host Runner).
Muestrea continuamente 'docker stats --no-stream' para registrar picos reales de CPU y RAM
durante toda la duración de un escalón de prueba de carga.
"""

import argparse
import subprocess
import time
import re
import sys

def parse_mem(mem_str):
    """Convierte string de memoria (ej. '630.8MiB') a float en MiB."""
    match = re.match(r"([\d\.]+)\s*([a-zA-Z]+)", mem_str.strip())
    if not match:
        return 0.0
    val, unit = float(match.group(1)), match.group(2).lower()
    if "gib" in unit or "gb" in unit:
        return val * 1024.0
    elif "kib" in unit or "kb" in unit:
        return val / 1024.0
    return val

def main():
    parser = argparse.ArgumentParser(description="Muestreo Continuo de Recursos Docker")
    parser.add_argument("--duration", type=int, default=315, help="Duración en segundos")
    parser.add_argument("--interval", type=int, default=2, help="Intervalo en segundos")
    args = parser.parse_args()

    tracked_containers = [
        "bulonera_web_local",
        "bulonera_web_load_locust",
        "bulonera_web_db_mariadb",
        "bulonera_web_redis"
    ]

    stats_data = {
        c: {
            "peak_cpu": 0.0,
            "cpu_samples": [],
            "peak_mem_mib": 0.0,
            "peak_raw_mem": ""
        } for c in tracked_containers
    }
    start_time = time.time()
    sample_count = 0

    print(f"Iniciando monitoreo de CPU/RAM para {args.duration}s (intervalo solicitado: {args.interval}s)...")

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= args.duration:
                break

            sample_count += 1
            try:
                cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}},{{.CPUPerc}},{{.MemUsage}}"]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                for line in res.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        name, cpu_str, mem_str = parts[0], parts[1], parts[2]
                        if name in stats_data:
                            cpu_val = float(cpu_str.replace("%", "").strip() or 0.0)
                            mem_usage_only = mem_str.split("/")[0].strip()
                            mem_mib = parse_mem(mem_usage_only)

                            stats_data[name]["cpu_samples"].append(cpu_val)
                            if cpu_val > stats_data[name]["peak_cpu"]:
                                stats_data[name]["peak_cpu"] = cpu_val
                            if mem_mib > stats_data[name]["peak_mem_mib"]:
                                stats_data[name]["peak_mem_mib"] = mem_mib
                                stats_data[name]["peak_raw_mem"] = mem_usage_only
            except Exception as e:
                pass

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

    final_elapsed = int(time.time() - start_time)
    cadence = (final_elapsed / sample_count) if sample_count > 0 else 0.0

    print("\n" + "=" * 65)
    print("RESUMEN DE RECURSOS DOCKER (MUESTREO CONTINUO)")
    print("=" * 65)
    print(f"Duración: {final_elapsed}s | Muestras: {sample_count} | Cadencia real: {cadence:.2f}s/muestra\n")
    for c in tracked_containers:
        d = stats_data[c]
        samples = d["cpu_samples"]
        avg_cpu = (sum(samples) / len(samples)) if samples else 0.0
        gt_100 = sum(1 for s in samples if s >= 100.0)
        gt_200 = sum(1 for s in samples if s >= 200.0)
        print(f"  * {c:<26}:")
        print(f"      - CPU: Pico {d['peak_cpu']:>6.2f}% | Media: {avg_cpu:>6.2f}% (Muestras >=100%: {gt_100}, >=200%: {gt_200})")
        print(f"      - RAM Contenedor: Pico {d['peak_raw_mem'] or 'N/A'}")
    print("=" * 65)

if __name__ == "__main__":
    main()

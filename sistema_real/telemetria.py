# archivo: sistema_real/telemetria.py
"""
Telemetria de la API: registra CADA peticion HTTP en datos/telemetry_log.csv.

Columnas:
    timestamp_iso        marca de tiempo UTC de la respuesta
    metodo               GET/POST/...
    ruta                 endpoint invocado
    status               codigo HTTP
    tiempo_respuesta_ms  latencia medida de la peticion
    pool_en_uso          conexiones del pool ocupadas (uso real de recurso, C6)
    pool_limite          limite duro C6 (50)
    tickets_abiertos     tickets en cola/atencion (uso simulado de recursos)

Es el insumo real para la seccion de Telemetria del INFORME_FINAL.md.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CSV = Path(os.getenv("TELEMETRY_PATH", RAIZ / "datos" / "telemetry_log.csv"))

_CABECERA = [
    "timestamp_iso", "metodo", "ruta", "status",
    "tiempo_respuesta_ms", "pool_en_uso", "pool_limite", "tickets_abiertos",
]

_lock = threading.Lock()


def _asegurar_cabecera() -> None:
    RUTA_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not RUTA_CSV.exists() or RUTA_CSV.stat().st_size == 0:
        with open(RUTA_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_CABECERA)


def registrar(metodo: str, ruta: str, status: int, tiempo_ms: float,
              pool_en_uso: int, pool_limite: int, tickets_abiertos: int) -> None:
    """Agrega una fila a la telemetria (thread-safe)."""
    with _lock:
        _asegurar_cabecera()
        with open(RUTA_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                dt.datetime.utcnow().isoformat(timespec="milliseconds"),
                metodo, ruta, status,
                round(tiempo_ms, 3), pool_en_uso, pool_limite, tickets_abiertos,
            ])


def resumen() -> dict:
    """Agrega la telemetria capturada (para el endpoint /metricas)."""
    if not RUTA_CSV.exists():
        return {"muestras": 0}
    lat, pool_max = [], 0
    with open(RUTA_CSV, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            try:
                lat.append(float(fila["tiempo_respuesta_ms"]))
                pool_max = max(pool_max, int(fila["pool_en_uso"]))
            except (ValueError, KeyError):
                continue
    if not lat:
        return {"muestras": 0}
    lat.sort()
    n = len(lat)
    p95 = lat[min(int(0.95 * n), n - 1)]
    p99 = lat[min(int(0.99 * n), n - 1)]
    return {
        "muestras": n,
        "latencia_media_ms": round(sum(lat) / n, 3),
        "latencia_p95_ms": round(p95, 3),
        "latencia_p99_ms": round(p99, 3),
        "pool_pico_en_uso": pool_max,
    }
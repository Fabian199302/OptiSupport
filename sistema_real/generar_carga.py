# archivo: sistema_real/generar_carga.py
"""
Generador de carga para la API OptiSupport.

Lanza peticiones contra la API siguiendo un proceso de llegadas Poisson con la
MISMA tasa de la simulacion (lambda), produciendo telemetria REAL en
datos/telemetry_log.csv (latencias, uso del pool C6, tickets abiertos).

Uso (con la API levantada en docker compose):
    python sistema_real/generar_carga.py --n 300 --url http://localhost:8000
    # o por duracion simulada:
    python sistema_real/generar_carga.py --minutos 10 --acelerado

Opcion --acelerado comprime el tiempo entre llegadas (no espera en tiempo real)
para generar telemetria rapido en una demostracion.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
from config.parametros import P  # noqa: E402


def generar(url: str, n: int, minutos: float, acelerado: bool, semilla: int) -> None:
    rng = random.Random(semilla)
    creados, errores = 0, 0
    t_sim = 0.0
    objetivo_n = n if n > 0 else None

    print(f"[carga] Enviando tickets a {url} (lambda={P.lambda_valle}/min, "
          f"{'modo acelerado' if acelerado else 'tiempo real'}) ...")

    inicio = time.time()
    while True:
        if objetivo_n is not None and creados >= objetivo_n:
            break
        if objetivo_n is None and t_sim >= minutos:
            break

        dt = rng.expovariate(P.lambda_valle)   # minutos hasta la siguiente llegada
        t_sim += dt
        if not acelerado:
            time.sleep(min(dt * 60.0, 2.0))     # a tiempo real (cap 2s por paso)

        tipo = rng.choices(list(P.tipos), weights=list(P.mezcla_tipos))[0]
        prioridad = rng.choices(list(P.prioridades), weights=list(P.mezcla_prioridades))[0]
        try:
            r = requests.post(f"{url}/tickets",
                              json={"tipo": tipo, "prioridad": prioridad}, timeout=5)
            if r.status_code == 201:
                creados += 1
            else:
                errores += 1
        except requests.RequestException as exc:
            errores += 1
            if errores <= 3:
                print(f"[carga] Error de conexion: {exc}")

    # Algunas consultas de estado para enriquecer la telemetria de lectura.
    for _ in range(max(creados // 10, 1)):
        try:
            requests.get(f"{url}/estado", timeout=5)
        except requests.RequestException:
            pass

    dur = time.time() - inicio
    print(f"[carga] Listo: {creados} tickets creados, {errores} errores, "
          f"{dur:.1f}s reales. Telemetria en datos/telemetry_log.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generador de carga de OptiSupport")
    ap.add_argument("--url", default="http://localhost:8000", help="URL base de la API")
    ap.add_argument("--n", type=int, default=300, help="numero de tickets a crear")
    ap.add_argument("--minutos", type=float, default=0.0,
                    help="minutos simulados (si >0, ignora --n)")
    ap.add_argument("--acelerado", action="store_true",
                    help="no esperar en tiempo real entre llegadas")
    ap.add_argument("--semilla", type=int, default=42)
    args = ap.parse_args()
    n = 0 if args.minutos > 0 else args.n
    generar(args.url, n, args.minutos, args.acelerado, args.semilla)
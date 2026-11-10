# archivo: simulacion/main.py
"""
Punto de entrada de la simulacion DES de OptiSupport.

Ejecuta, para 3 escenarios, N replicas independientes con semillas fijas,
agrega los KPIs (media +/- IC95, p95/p99) y escribe:

    simulacion/resultados_simulacion.json     (consumido por analisis/)
    docs/figuras/politicas_kpis.png
    docs/figuras/perfil_llegadas.png

Escenarios:
    1. markoviano_base : modo markoviano + Round Robin  -> valida contra M/M/c
    2. roundrobin_real : modo real      + Round Robin  -> POLITICA ACTUAL (base)
    3. skillbased_real : modo real      + Skill-Based  -> POLITICA ALTERNATIVA

Uso:
    python simulacion/main.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List

# Permite ejecutar como `python simulacion/main.py` desde la raiz del repo.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import simpy  # noqa: E402

from config.parametros import P  # noqa: E402
from simulacion.estrategias import crear_estrategia  # noqa: E402
from simulacion.estadisticas import RecolectorEstadisticas, agregar_replicas  # noqa: E402
from simulacion.modelo import SimuladorOrquestador  # noqa: E402

RUTA_JSON = RAIZ / "simulacion" / "resultados_simulacion.json"
RUTA_FIGURAS = RAIZ / "docs" / "figuras"


def correr_replica(modo: str, estrategia_nombre: str, semilla: int,
                   horizonte: float, warmup: float) -> Dict[str, float]:
    """Ejecuta UNA replica y devuelve sus KPIs."""
    rng = random.Random(semilla)
    env = simpy.Environment()
    recolector = RecolectorEstadisticas(
        warmup_min=warmup,
        horizonte_min=horizonte,
        c_tecnicos=P.c_tecnicos,
    )
    estrategia = crear_estrategia(estrategia_nombre)
    sim = SimuladorOrquestador(env, P, estrategia, rng, recolector, modo=modo,
                               horizonte_min=horizonte, warmup_min=warmup)
    env.run(until=horizonte)
    sim.finalizar()
    return recolector.kpis()


def correr_escenario(modo: str, estrategia_nombre: str) -> Dict:
    """Corre las N replicas de un escenario y agrega los resultados."""
    # El contraste markoviano usa horizonte largo (regimen estacionario);
    # los escenarios reales usan la jornada operativa de 8 h.
    if modo == "markoviano":
        horizonte, warmup = P.horizonte_validacion_min, P.warmup_validacion_min
    else:
        horizonte, warmup = P.horizonte_min, P.warmup_min
    kpis = [correr_replica(modo, estrategia_nombre, s, horizonte, warmup)
            for s in P.semillas]
    agregado = agregar_replicas(kpis)
    agregado["config"] = {
        "modo": modo, "estrategia": estrategia_nombre,
        "horizonte_min": horizonte, "warmup_min": warmup,
    }
    return agregado


def main() -> None:
    print("=" * 70)
    print(" OptiSupport  ·  Simulacion DES  (SimPy)")
    print("=" * 70)
    print(f"  Horizonte={P.horizonte_min:.0f} min | warm-up={P.warmup_min:.0f} min "
          f"| replicas={P.n_replicas} | semillas {P.semilla_base}..{P.semilla_base + P.n_replicas - 1}")
    print(f"  lambda_valle={P.lambda_valle} | lambda_pico={P.lambda_pico} "
          f"| servicio={P.tiempo_servicio_min} min | c={P.c_tecnicos} | rho={P.rho_base:.3f}")
    print("-" * 70)

    escenarios = {
        "markoviano_base": ("markoviano", "round_robin"),
        "roundrobin_real": ("real", "round_robin"),
        "skillbased_real": ("real", "skill_based"),
    }

    resultados: Dict[str, Dict] = {
        "parametros": P.resumen(),
        "escenarios": {},
    }

    for nombre, (modo, estrategia) in escenarios.items():
        print(f"  Ejecutando escenario: {nombre:<18} (modo={modo}, politica={estrategia}) ...")
        resultados["escenarios"][nombre] = correr_escenario(modo, estrategia)
        r = resultados["escenarios"][nombre]
        print(f"      W_p95 = {r['W_p95_min']['media']:.2f} min   "
              f"abandono = {100 * r['tasa_abandono']['media']:.2f}%   "
              f"utilizacion = {100 * r['utilizacion']['media']:.1f}%")

    RUTA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print("-" * 70)
    print(f"  [OK] Resultados escritos en: {RUTA_JSON.relative_to(RAIZ)}")

    try:
        generar_figuras(resultados)
        print(f"  [OK] Figuras escritas en:    {RUTA_FIGURAS.relative_to(RAIZ)}/")
    except Exception as exc:  # matplotlib opcional
        print(f"  [WARN] No se generaron figuras ({exc}). Instala matplotlib.")
    print("=" * 70)


# ---------------------------------------------------------------------- #
#  Figuras
# ---------------------------------------------------------------------- #
def generar_figuras(resultados: Dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    RUTA_FIGURAS.mkdir(parents=True, exist_ok=True)
    esc = resultados["escenarios"]
    rr = esc["roundrobin_real"]
    sb = esc["skillbased_real"]

    # --- Figura 1: KPIs por politica con umbrales SLA ---
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    politicas = ["Round Robin\n(Actual)", "Skill-Based\n(Alternativa)"]
    colores = ["#4C72B0", "#55A868"]

    # p95 del tiempo total
    vals = [rr["W_p95_min"]["media"], sb["W_p95_min"]["media"]]
    errs = [rr["W_p95_min"]["ic95_semiancho"], sb["W_p95_min"]["ic95_semiancho"]]
    axes[0].bar(politicas, vals, yerr=errs, capsize=6, color=colores)
    axes[0].axhline(P.sla_p95_atencion_min, ls="--", color="red",
                    label=f"SLA p95 = {P.sla_p95_atencion_min:.0f} min")
    axes[0].set_ylabel("Tiempo total p95 (min)")
    axes[0].set_title("p95 del tiempo de atencion")
    axes[0].legend(fontsize=8)

    # abandono
    vals = [100 * rr["tasa_abandono"]["media"], 100 * sb["tasa_abandono"]["media"]]
    errs = [100 * rr["tasa_abandono"]["ic95_semiancho"],
            100 * sb["tasa_abandono"]["ic95_semiancho"]]
    axes[1].bar(politicas, vals, yerr=errs, capsize=6, color=colores)
    axes[1].axhline(100 * P.sla_abandono_max, ls="--", color="red",
                    label=f"SLA abandono = {100 * P.sla_abandono_max:.0f}%")
    axes[1].set_ylabel("Tasa de abandono (%)")
    axes[1].set_title("Abandono por paciencia")
    axes[1].legend(fontsize=8)

    # utilizacion
    vals = [100 * rr["utilizacion"]["media"], 100 * sb["utilizacion"]["media"]]
    errs = [100 * rr["utilizacion"]["ic95_semiancho"],
            100 * sb["utilizacion"]["ic95_semiancho"]]
    axes[2].bar(politicas, vals, yerr=errs, capsize=6, color=colores)
    axes[2].axhspan(100 * P.sla_utilizacion_min, 100 * P.sla_utilizacion_max,
                    color="green", alpha=0.12, label="Banda objetivo 70-85%")
    axes[2].set_ylabel("Utilizacion de tecnicos (%)")
    axes[2].set_title("Utilizacion del cuello de botella")
    axes[2].legend(fontsize=8)

    fig.suptitle("OptiSupport — KPIs por politica (media +/- IC95, N=%d replicas)"
                 % P.n_replicas, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(RUTA_FIGURAS / "politicas_kpis.png", dpi=130)
    plt.close(fig)

    # --- Figura 2: Perfil de llegadas no estacionario ---
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ts = np.linspace(0, P.horizonte_min, 1000)
    lam = []
    for t in ts:
        en_pico = any(ini <= t < fin for ini, fin in P.ventanas_pico)
        lam.append(P.lambda_pico if en_pico else P.lambda_valle)
    ax.plot(ts, lam, color="#C44E52", lw=2)
    ax.fill_between(ts, lam, color="#C44E52", alpha=0.15)
    ax.set_xlabel("Minuto de la jornada (08:00 = 0)")
    ax.set_ylabel("lambda(t)  [tickets/min]")
    ax.set_title("Perfil de llegadas no estacionario (valle 0.5 / pico 1.5)")
    ax.set_ylim(0, P.lambda_pico * 1.25)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RUTA_FIGURAS / "perfil_llegadas.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()

# Revision de parametros - Yulisa

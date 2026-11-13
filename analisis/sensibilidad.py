"""
Analisis de sensibilidad de OptiSupport.

Uso desde la raiz del repositorio:
    python analisis/sensibilidad.py

Ejecuta 30 replicas por escenario con las semillas del modelo y varia un
parametro a la vez: factor de servicio especialista, tecnicos y pool C6.
Imprime los resultados en tablas Markdown para el informe final.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import config.parametros as cfg  # noqa: E402
import simulacion.main as sim_main  # noqa: E402

P_BASE = cfg.P


def correr(**cambios: float | int) -> dict[str, Any]:
    """Ejecuta ambos modelos reales con una copia modificada de P."""
    parametros = dataclasses.replace(P_BASE, **cambios)
    sim_main.P = parametros
    try:
        return {
            politica: sim_main.correr_escenario("real", politica)
            for politica in ("round_robin", "skill_based")
        }
    finally:
        sim_main.P = P_BASE


def celda(resultado: dict[str, Any], clave: str, escala: float = 1.0,
          decimales: int = 1) -> str:
    kpi = resultado[clave]
    return (
        f"{escala * kpi['media']:.{decimales}f} ± "
        f"{escala * kpi['ic95_semiancho']:.{decimales}f}"
    )


def fila(etiqueta: str, resultado: dict[str, Any]) -> str:
    return (
        f"| {etiqueta} | {celda(resultado, 'tasa_abandono', 100)} | "
        f"{celda(resultado, 'W_p95_min')} | "
        f"{celda(resultado, 'W_p99_min')} | "
        f"{celda(resultado, 'utilizacion', 100)} | "
        f"{resultado['totales']['rechazados']} |"
    )


def imprimir_tabla(encabezado: str, filas: list[tuple[str, dict[str, Any]]]) -> None:
    print(f"| {encabezado} | Abandono (%) | p95 (min) | p99 (min) | "
          "Utilizacion (%) | Rechazos C6 |")
    print("|---|---:|---:|---:|---:|---:|")
    for etiqueta, resultado in filas:
        print(fila(etiqueta, resultado))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("# Analisis de sensibilidad")
    print(
        f"30 replicas por escenario; semillas {P_BASE.semilla_base}.."
        f"{P_BASE.semilla_base + P_BASE.n_replicas - 1}; "
        "modo real; se varia un parametro a la vez.\n"
    )

    print("## Factor de servicio del especialista (c = 9)\n")
    filas_factor = []
    for factor in (0.80, 0.90, 1.00):
        resultados = correr(servicio_skill_factor=factor)
        if factor == 0.80:
            filas_factor.append(
                ("Round Robin (no usa el factor)", resultados["round_robin"])
            )
        filas_factor.append(
            (f"Skill-Based, factor {factor:.2f}", resultados["skill_based"])
        )
    imprimir_tabla("Factor / politica", filas_factor)

    print("\n## Numero de tecnicos (factor de servicio 0.80)\n")
    filas_tecnicos = []
    for tecnicos in (9, 10, 11, 12):
        resultados = correr(c_tecnicos=tecnicos)
        filas_tecnicos.extend(
            (
                (f"c = {tecnicos}, Round Robin", resultados["round_robin"]),
                (f"c = {tecnicos}, Skill-Based", resultados["skill_based"]),
            )
        )
    imprimir_tabla("Tecnicos / politica", filas_tecnicos)

    print("\n## Pool de conexiones C6 (c = 9, Skill-Based)\n")
    filas_pool = []
    for capacidad in (50, 5, 1):
        resultados = correr(pool_conexiones=capacidad)
        filas_pool.append(
            (f"Pool = {capacidad}", resultados["skill_based"])
        )
    imprimir_tabla("Capacidad del pool", filas_pool)


if __name__ == "__main__":
    main()

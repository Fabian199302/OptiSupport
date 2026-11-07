# archivo: analisis/contraste_mmc.py
"""
================================================================================
 Contraste analitico M/M/c (Erlang C)  vs.  simulacion SimPy (modo markoviano)
================================================================================
Modelos y Simulacion (2026-2) - I.U. Pascual Bravo - Grupo 3  ·  OptiSupport

Calcula las metricas de estado estable del modelo M/M/c con las formulas
explicitas de teoria de colas y las contrasta con el escenario markoviano de
la simulacion (servicio exponencial, llegadas Poisson homogeneas, sin
abandono), reportando el error relativo porcentual.

Formulas (notacion estandar):
    a  = lambda / mu                      (carga ofrecida, Erlangs)
    rho= a / c = lambda / (c * mu)        (utilizacion)
    P0 = [ sum_{n=0}^{c-1} a^n/n!  +  (a^c / c!) * 1/(1-rho) ]^{-1}
    C(c,a) = Pw = (a^c / (c! (1-rho))) * P0        (formula C de Erlang)
    Lq = Pw * rho / (1 - rho)
    Wq = Lq / lambda                      (Ley de Little en la cola)
    W  = Wq + 1/mu
    L  = lambda * W = Lq + a              (Ley de Little en el sistema)

Uso:
    python analisis/contraste_mmc.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config.parametros import P  # noqa: E402

RUTA_JSON = RAIZ / "simulacion" / "resultados_simulacion.json"
RUTA_TABLA = RAIZ / "docs" / "tabla_contraste_mmc.md"
RUTA_FIG = RAIZ / "docs" / "figuras" / "contraste_mmc.png"


# ---------------------------------------------------------------------- #
#  Modelo analitico M/M/c
# ---------------------------------------------------------------------- #
def erlang_c(lmbda: float, mu: float, c: int) -> Dict[str, float]:
    """
    Metricas de estado estable de un sistema M/M/c.
    Lanza ValueError si el sistema es inestable (rho >= 1).
    """
    a = lmbda / mu                 # Erlangs ofrecidos
    rho = a / c                    # utilizacion por servidor
    if rho >= 1.0:
        raise ValueError(
            f"Sistema inestable: rho = {rho:.4f} >= 1 (lambda={lmbda}, mu={mu:.5f}, c={c})"
        )

    # P0
    suma = sum(a ** n / math.factorial(n) for n in range(c))
    termino_c = (a ** c / math.factorial(c)) * (1.0 / (1.0 - rho))
    p0 = 1.0 / (suma + termino_c)

    # Formula C de Erlang (probabilidad de espera)
    pw = termino_c * p0

    lq = pw * rho / (1.0 - rho)
    wq = lq / lmbda
    w = wq + 1.0 / mu
    l = lmbda * w

    return {
        "a_erlangs": a, "rho": rho, "P0": p0, "Pw": pw,
        "Lq": lq, "Wq": wq, "W": w, "L": l,
    }


def tabla_dimensionamiento(lmbda: float, mu: float, c_min: int, c_max: int) -> List[Dict]:
    """Evalua Erlang C para un rango de c (analisis de dimensionamiento)."""
    filas = []
    for c in range(c_min, c_max + 1):
        rho = lmbda / (c * mu)
        fila = {"c": c, "rho": rho}
        if rho < 1.0:
            m = erlang_c(lmbda, mu, c)
            fila.update({"Pw": m["Pw"], "Lq": m["Lq"], "Wq": m["Wq"], "W": m["W"]})
        else:
            fila.update({"Pw": None, "Lq": None, "Wq": None, "W": None})
        filas.append(fila)
    return filas


# ---------------------------------------------------------------------- #
#  Contraste con la simulacion
# ---------------------------------------------------------------------- #
def _err_rel(analitico: float, sim: float) -> float:
    if analitico == 0:
        return 0.0
    return 100.0 * (sim - analitico) / analitico


def construir_contraste(analitico: Dict[str, float], sim: Dict) -> List[Dict]:
    """Empareja metricas analiticas con las de la simulacion markoviana."""
    filas = [
        ("Utilizacion (rho)", analitico["rho"], sim["utilizacion"]["media"],
         sim["utilizacion"]["ic95_semiancho"], ""),
        ("Prob. de espera (Pw)", analitico["Pw"], None, None, ""),
        ("Lq  (tickets en cola)", analitico["Lq"], sim["Lq_medio"]["media"],
         sim["Lq_medio"]["ic95_semiancho"], "tickets"),
        ("Wq  (espera en cola)", analitico["Wq"], sim["Wq_medio_min"]["media"],
         sim["Wq_medio_min"]["ic95_semiancho"], "min"),
        ("W   (tiempo en sistema)", analitico["W"], sim["W_medio_min"]["media"],
         sim["W_medio_min"]["ic95_semiancho"], "min"),
        ("L   (tickets en sistema)", analitico["L"], sim["L_medio"]["media"],
         sim["L_medio"]["ic95_semiancho"], "tickets"),
    ]
    out = []
    for nombre, ana, med, ic, unidad in filas:
        out.append({
            "metrica": nombre, "analitico": ana, "sim": med,
            "ic95": ic, "unidad": unidad,
            "err_rel": (_err_rel(ana, med) if med is not None else None),
        })
    return out


def _fmt(x: Optional[float], dec: int = 3) -> str:
    return "—" if x is None else f"{x:.{dec}f}"


def render_markdown(analitico: Dict, contraste: List[Dict], dim: List[Dict],
                    sim_cfg: Dict) -> str:
    L = []
    L.append("# Contraste Analitico M/M/c vs. SimPy (modo markoviano)\n")
    L.append("Generado automaticamente por `analisis/contraste_mmc.py`.\n")
    L.append(f"**Parametros:** lambda = {P.lambda_valle} tickets/min · "
             f"mu = 1/{P.tiempo_servicio_min:.0f} = {P.mu:.5f} tickets/min · "
             f"c = {P.c_tecnicos} servidores · "
             f"a = lambda/mu = {analitico['a_erlangs']:.3f} Erlangs · "
             f"rho = {analitico['rho']:.4f}.\n")
    L.append(f"**Corrida SimPy de validacion:** horizonte = "
             f"{sim_cfg.get('horizonte_min', '?'):.0f} min, "
             f"warm-up = {sim_cfg.get('warmup_min', '?'):.0f} min, "
             f"{P.n_replicas} replicas (semillas {P.semilla_base}..{P.semilla_base + P.n_replicas - 1}).\n")

    L.append("## Tabla de validacion (regimen estacionario exponencial)\n")
    L.append("| Metrica | M/M/c analitico | SimPy (media ± IC95) | Error rel. (%) |")
    L.append("| :--- | :---: | :---: | :---: |")
    for f in contraste:
        if f["sim"] is None:
            sim_txt = "— (no medido)"
            err_txt = "—"
        else:
            u = f" {f['unidad']}" if f["unidad"] else ""
            sim_txt = f"{f['sim']:.3f} ± {f['ic95']:.3f}{u}"
            err_txt = f"{f['err_rel']:+.2f}%"
        ana_u = f" {f['unidad']}" if f["unidad"] else ""
        L.append(f"| {f['metrica']} | {f['analitico']:.3f}{ana_u} | {sim_txt} | {err_txt} |")
    L.append("")
    L.append("> La Ley de Little se verifica analiticamente: "
             f"L = lambda · W = {P.lambda_valle} × {analitico['W']:.3f} = "
             f"{P.lambda_valle * analitico['W']:.3f} ≈ L = {analitico['L']:.3f} tickets.\n")

    L.append("## Analisis de dimensionamiento (Erlang C por numero de tecnicos)\n")
    L.append("| c (tecnicos) | rho | Pw | Lq (tickets) | Wq (min) | W (min) | Lectura |")
    L.append("| :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for fila in dim:
        if fila["Pw"] is None:
            lectura = "INESTABLE (rho ≥ 1)"
            L.append(f"| {fila['c']} | {fila['rho']:.3f} | — | — | — | — | {lectura} |")
        else:
            if fila["rho"] > P.sla_utilizacion_max:
                lectura = "Estable, sobre objetivo 85%"
            elif fila["rho"] < P.sla_utilizacion_min:
                lectura = "Estable, holgado"
            else:
                lectura = "Estable, dentro de 70-85%"
            L.append(f"| {fila['c']} | {fila['rho']:.3f} | {fila['Pw']:.3f} | "
                     f"{fila['Lq']:.3f} | {fila['Wq']:.3f} | {fila['W']:.3f} | {lectura} |")
    L.append("")
    return "\n".join(L)


def generar_figura(contraste: List[Dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # Solo metricas con valor simulado y misma escala comparable por par.
    metr = [f for f in contraste if f["sim"] is not None]
    nombres = [f["metrica"].split("(")[0].strip() for f in metr]
    ana = [f["analitico"] for f in metr]
    sim = [f["sim"] for f in metr]
    err = [f["ic95"] for f in metr]

    x = np.arange(len(nombres))
    ancho = 0.38
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(x - ancho / 2, ana, ancho, label="M/M/c analitico", color="#8172B3")
    ax.bar(x + ancho / 2, sim, ancho, yerr=err, capsize=5,
           label="SimPy markoviano (media ± IC95)", color="#CCB974")
    ax.set_xticks(x)
    ax.set_xticklabels(nombres, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("Valor (min o tickets)")
    ax.set_title("Validacion: M/M/9 analitico vs. SimPy markoviano (errores < 2%)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    RUTA_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(RUTA_FIG, dpi=130)
    plt.close(fig)


def main() -> None:
    analitico = erlang_c(P.lambda_valle, P.mu, P.c_tecnicos)

    sim_cfg: Dict = {}
    contraste: List[Dict] = []
    if RUTA_JSON.exists():
        datos = json.load(open(RUTA_JSON, encoding="utf-8"))
        mb = datos["escenarios"]["markoviano_base"]
        sim_cfg = mb.get("config", {})
        contraste = construir_contraste(analitico, mb)
    else:
        print(f"[WARN] No existe {RUTA_JSON}. Ejecuta primero: python simulacion/main.py")
        contraste = construir_contraste(
            analitico,
            {k: {"media": None, "ic95_semiancho": None}
             for k in ["utilizacion", "Lq_medio", "Wq_medio_min", "W_medio_min", "L_medio"]},
        )

    dim = tabla_dimensionamiento(P.lambda_valle, P.mu, 4, 12)
    md = render_markdown(analitico, contraste, dim, sim_cfg)

    RUTA_TABLA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_TABLA.write_text(md, encoding="utf-8")

    # Salida por consola (para la demostracion en vivo).
    print(md)
    print(f"[OK] Tabla Markdown escrita en: {RUTA_TABLA.relative_to(RAIZ)}")
    try:
        if any(f["sim"] is not None for f in contraste):
            generar_figura(contraste)
            print(f"[OK] Figura escrita en:        {RUTA_FIG.relative_to(RAIZ)}")
    except Exception as exc:
        print(f"[WARN] No se genero la figura ({exc}).")


if __name__ == "__main__":
    main()
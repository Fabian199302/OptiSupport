# archivo: simulacion/estadisticas.py
"""
Recoleccion y agregacion estadistica de los KPIs de la simulacion.

- `RecolectorEstadisticas` : registra eventos de UNA replica.
- funciones de agregacion   : media, desviacion, IC95 y percentiles sobre
                              las R replicas independientes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .entidades import Ticket, Estado


@dataclass
class RecolectorEstadisticas:
    """
    Acumula las observaciones de una unica corrida (replica).

    Solo se contabilizan los tickets que LLEGAN despues del warm-up, para
    estimar metricas en regimen y no el transitorio de arranque.
    """
    warmup_min: float
    horizonte_min: float
    c_tecnicos: int

    tiempos_totales: List[float] = field(default_factory=list)   # W por ticket (min)
    esperas_cola: List[float] = field(default_factory=list)      # Wq por ticket (min)
    llegados: int = 0
    resueltos: int = 0
    abandonados: int = 0
    rechazados: int = 0
    reintentos: int = 0
    tiempo_ocupado_total: float = 0.0   # suma de minutos-tecnico ocupados (post warm-up)
    # Area bajo L(t) y Lq(t) para estimar L y Lq por integracion.
    _area_L: float = 0.0
    _area_Lq: float = 0.0
    _t_ultimo: float = 0.0
    _L_actual: int = 0
    _Lq_actual: int = 0

    def en_ventana(self, t: float) -> bool:
        """True si el instante pertenece al periodo de medicion (post warm-up)."""
        return t >= self.warmup_min

    # ---- Integracion temporal de L(t) y Lq(t) ----
    def _avanzar_areas(self, t: float) -> None:
        if t > self._t_ultimo:
            if t >= self.warmup_min:
                ini = max(self._t_ultimo, self.warmup_min)
                dt = t - ini
                if dt > 0:
                    self._area_L += self._L_actual * dt
                    self._area_Lq += self._Lq_actual * dt
            self._t_ultimo = t

    def set_estado_sistema(self, t: float, en_sistema: int, en_cola: int) -> None:
        self._avanzar_areas(t)
        self._L_actual = en_sistema
        self._Lq_actual = en_cola

    # ---- Registro de eventos ----
    def registrar_llegada(self, t: float, es_reintento: bool = False) -> None:
        if self.en_ventana(t):
            self.llegados += 1
            if es_reintento:
                self.reintentos += 1

    def registrar_resuelto(self, ticket: Ticket) -> None:
        if self.en_ventana(ticket.t_llegada):
            self.resueltos += 1
            if ticket.tiempo_total is not None:
                self.tiempos_totales.append(ticket.tiempo_total)
            if ticket.espera_cola is not None:
                self.esperas_cola.append(ticket.espera_cola)

    def registrar_abandono(self, ticket: Ticket) -> None:
        if self.en_ventana(ticket.t_llegada):
            self.abandonados += 1
            if ticket.espera_cola is not None:
                self.esperas_cola.append(ticket.espera_cola)

    def registrar_rechazo(self, ticket: Ticket) -> None:
        if self.en_ventana(ticket.t_llegada):
            self.rechazados += 1

    def registrar_ocupacion(self, minutos: float) -> None:
        self.tiempo_ocupado_total += minutos

    # ---- KPIs de la replica ----
    def kpis(self) -> Dict[str, float]:
        ventana = max(self.horizonte_min - self.warmup_min, 1e-9)
        arr = np.array(self.tiempos_totales) if self.tiempos_totales else np.array([0.0])
        esp = np.array(self.esperas_cola) if self.esperas_cola else np.array([0.0])
        base_aband = max(self.llegados, 1)
        return {
            "W_medio_min": float(arr.mean()),
            "W_p95_min": float(np.percentile(arr, 95)),
            "W_p99_min": float(np.percentile(arr, 99)),
            "Wq_medio_min": float(esp.mean()),
            "tasa_abandono": self.abandonados / base_aband,
            "tasa_rechazo": self.rechazados / base_aband,
            "utilizacion": self.tiempo_ocupado_total / (self.c_tecnicos * ventana),
            "L_medio": self._area_L / ventana,
            "Lq_medio": self._area_Lq / ventana,
            "llegados": self.llegados,
            "resueltos": self.resueltos,
            "abandonados": self.abandonados,
            "rechazados": self.rechazados,
            "reintentos": self.reintentos,
        }


def _ic95(muestras: List[float]) -> Dict[str, float]:
    """Media, desviacion y semiancho del IC95 (t de Student) de una muestra."""
    x = np.array(muestras, dtype=float)
    n = len(x)
    media = float(x.mean())
    if n < 2:
        return {"media": media, "desv": 0.0, "ic95_semiancho": 0.0, "n": n}
    desv = float(x.std(ddof=1))
    # t critico aproximado 95% (n-1 gl). Para n>=30 ~ 2.045..2.0.
    t_crit = _t_student_95(n - 1)
    semiancho = t_crit * desv / math.sqrt(n)
    return {"media": media, "desv": desv, "ic95_semiancho": semiancho, "n": n}


def _t_student_95(gl: int) -> float:
    """Valor critico t de dos colas al 95% (tabla compacta)."""
    tabla = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086,
        25: 2.060, 29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
    }
    if gl in tabla:
        return tabla[gl]
    claves = sorted(tabla)
    for k in claves:
        if gl <= k:
            return tabla[k]
    return 1.96  # n grande -> normal


def agregar_replicas(kpis_por_replica: List[Dict[str, float]]) -> Dict[str, Dict]:
    """
    Agrega la lista de KPIs (uno por replica) en estadisticos resumen:
    media, desviacion, IC95 y (para W) percentiles agregados.
    """
    claves = [
        "W_medio_min", "W_p95_min", "W_p99_min", "Wq_medio_min",
        "tasa_abandono", "tasa_rechazo", "utilizacion", "L_medio", "Lq_medio",
    ]
    resumen: Dict[str, Dict] = {}
    for k in claves:
        valores = [r[k] for r in kpis_por_replica]
        resumen[k] = _ic95(valores)
    # Totales de conteo (sumados sobre replicas)
    resumen["totales"] = {
        "llegados": int(sum(r["llegados"] for r in kpis_por_replica)),
        "resueltos": int(sum(r["resueltos"] for r in kpis_por_replica)),
        "abandonados": int(sum(r["abandonados"] for r in kpis_por_replica)),
        "rechazados": int(sum(r["rechazados"] for r in kpis_por_replica)),
        "reintentos": int(sum(r["reintentos"] for r in kpis_por_replica)),
        "replicas": len(kpis_por_replica),
    }
    return resumen
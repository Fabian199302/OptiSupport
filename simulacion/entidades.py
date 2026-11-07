# archivo: simulacion/entidades.py
"""
Entidades y recursos del modelo DES de OptiSupport.

- `Ticket`   : entidad que fluye por el sistema (Criterio C3/C7).
- `Tecnico`  : recurso finito y heterogeneo que atiende tickets (Criterio C1).

Coinciden con el diseno POO declarado en la Entrega 1 (clases `Ticket`,
`RecursoTecnico`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Set


class Estado(IntEnum):
    """Estados posibles de un ticket a lo largo de su ciclo de vida."""
    NUEVO = 0
    EN_COLA = 1
    EN_ATENCION = 2
    RESUELTO = 3
    ABANDONADO = 4
    RECHAZADO = 5       # sin conexion de pool disponible (C6)


@dataclass
class Ticket:
    """Entidad 'Ticket'. Un ticket es una unidad de trabajo de soporte."""
    id: int
    tipo: str                       # REDES / BD / INFRA
    prioridad: int                  # 1 = critico, 2 = alto, 3 = normal
    t_llegada: float                # minuto de llegada al sistema
    paciencia: float                # minutos que el usuario espera antes de abandonar
    reintento_num: int = 0          # cuantas veces este usuario ya reintento

    # Marcas temporales que se llenan durante la simulacion
    t_inicio_atencion: Optional[float] = None
    t_fin: Optional[float] = None
    estado: Estado = Estado.NUEVO
    tecnico_id: Optional[int] = None

    # --- Metricas derivadas (minutos) ---
    @property
    def espera_cola(self) -> Optional[float]:
        """Wq del ticket: tiempo en cola antes de iniciar atencion."""
        if self.t_inicio_atencion is None:
            return None
        return self.t_inicio_atencion - self.t_llegada

    @property
    def tiempo_total(self) -> Optional[float]:
        """W del ticket: tiempo total en el sistema (extremo a extremo)."""
        if self.t_fin is None:
            return None
        return self.t_fin - self.t_llegada


@dataclass
class Tecnico:
    """
    Recurso 'RecursoTecnico'. Servidor finito con especialidad (habilidades),
    disponibilidad y carga acumulada. En la politica base todos son
    generalistas; en Skill-Based cada uno tiene un subconjunto de habilidades.
    """
    id: int
    habilidades: Set[str]
    disponible: bool = True
    tickets_atendidos: int = 0
    tiempo_ocupado: float = 0.0     # minutos acumulados en atencion (para utilizacion)

    def puede_atender(self, tipo: str) -> bool:
        return tipo in self.habilidades
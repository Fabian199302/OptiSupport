# archivo: simulacion/estrategias.py
"""
Patron de diseno STRATEGY para las politicas de asignacion de tickets.

Interfaz:  `PoliticaEnrutamiento.asignar(cola, tecnicos) -> list[(Ticket, Tecnico)]`

El `SimuladorOrquestador` NO conoce la regla concreta: delega en la estrategia
inyectada. Esto permite intercambiar la politica sin tocar la logica del motor,
tal como se declaro en el diseno POO de la Entrega 1.

Politicas implementadas:
    - RoundRobinStrategy          (LINEA BASE / Politica Actual)
    - SkillBasedRoutingStrategy   (ALTERNATIVA)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

from .entidades import Ticket, Tecnico

Asignacion = Tuple[Ticket, Tecnico]


class PoliticaEnrutamiento(ABC):
    """Interfaz Strategy. La cola llega ya ordenada por (prioridad, FIFO)."""

    nombre: str = "base"

    @abstractmethod
    def asignar(self, cola: List[Ticket], tecnicos: List[Tecnico]) -> List[Asignacion]:
        """Devuelve la lista de emparejamientos (ticket, tecnico) a ejecutar."""
        raise NotImplementedError


class RoundRobinStrategy(PoliticaEnrutamiento):
    """
    POLITICA ACTUAL (linea base).

    Tecnicos GENERALISTAS (atienden cualquier tipo). Se recorre la cola en
    orden de prioridad y, dentro de la misma prioridad, FIFO; cada ticket se
    entrega al siguiente tecnico disponible siguiendo una rotacion circular.

    Es la politica mas cercana al modelo analitico M/M/c (servidores
    homogeneos, disciplina por prioridad + FIFO), por lo que sirve de
    referencia para la validacion.
    """
    nombre = "round_robin"

    def __init__(self) -> None:
        self._puntero = 0  # cursor de rotacion round-robin

    def asignar(self, cola: List[Ticket], tecnicos: List[Tecnico]) -> List[Asignacion]:
        asignaciones: List[Asignacion] = []
        disponibles = [t for t in tecnicos if t.disponible]
        if not disponibles:
            return asignaciones

        idx = 0
        for ticket in cola:
            if idx >= len(disponibles):
                break
            # Rotacion circular sobre los tecnicos disponibles en esta pasada.
            tecnico = disponibles[(self._puntero + idx) % len(disponibles)]
            asignaciones.append((ticket, tecnico))
            idx += 1
        self._puntero = (self._puntero + idx) % max(len(tecnicos), 1)
        return asignaciones


class SkillBasedRoutingStrategy(PoliticaEnrutamiento):
    """
    POLITICA ALTERNATIVA (Skill-Based Routing).

    Tecnicos ESPECIALIZADos: cada ticket se enruta a un tecnico que posea la
    habilidad de su tipo. Entre los tecnicos compatibles disponibles se elige
    el de MENOR carga acumulada (balanceo de carga), reduciendo los tiempos de
    espera de los tipos con mayor demanda.

    Referencias: Garnett & Mandelbaum (2000); Wallace & Whitt (2005).
    """
    nombre = "skill_based"

    def asignar(self, cola: List[Ticket], tecnicos: List[Tecnico]) -> List[Asignacion]:
        asignaciones: List[Asignacion] = []
        # Copia local de disponibilidad para no asignar dos veces en una pasada.
        libres = {t.id: t for t in tecnicos if t.disponible}

        for ticket in cola:
            candidatos = [
                t for t in libres.values() if t.puede_atender(ticket.tipo)
            ]
            if not candidatos:
                continue  # no hay tecnico compatible libre: el ticket sigue en cola
            # Menor carga primero (balanceo); desempate por id para reproducibilidad.
            elegido = min(candidatos, key=lambda t: (t.tiempo_ocupado, t.id))
            asignaciones.append((ticket, elegido))
            del libres[elegido.id]
            if not libres:
                break
        return asignaciones


# Fabrica para seleccionar la estrategia por nombre (usada por main.py).
ESTRATEGIAS = {
    RoundRobinStrategy.nombre: RoundRobinStrategy,
    SkillBasedRoutingStrategy.nombre: SkillBasedRoutingStrategy,
}


def crear_estrategia(nombre: str) -> PoliticaEnrutamiento:
    if nombre not in ESTRATEGIAS:
        raise ValueError(f"Estrategia desconocida: {nombre}. Opciones: {list(ESTRATEGIAS)}")
    return ESTRATEGIAS[nombre]()
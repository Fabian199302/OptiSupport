# archivo: simulacion/modelo.py
"""
SimuladorOrquestador: motor de simulacion de eventos discretos de OptiSupport.

Coordina reloj, llegadas, recursos (tecnicos + pool C6), politica de
asignacion (Strategy), abandonos (paciencia C7), reintentos y la recoleccion
de estadisticas.

Dos MODOS de corrida:
  - "markoviano": servicio Exponencial(media=15), llegadas Poisson homogeneas
    (lambda valle), SIN abandono/reintento y pool no restrictivo. Sirve para
    CONTRASTAR contra el modelo analitico M/M/c.
  - "real": servicio Lognormal (misma media, cola larga), llegadas NO
    estacionarias (picos), abandono por paciencia, reintentos y limite duro
    del pool (C6). Es el sistema que se usa para comparar POLITICAS.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional

import simpy

from config.parametros import Parametros
from .entidades import Ticket, Tecnico, Estado
from .estrategias import PoliticaEnrutamiento
from .estadisticas import RecolectorEstadisticas


class SimuladorOrquestador:
    def __init__(
        self,
        env: simpy.Environment,
        params: Parametros,
        estrategia: PoliticaEnrutamiento,
        rng: random.Random,
        recolector: RecolectorEstadisticas,
        modo: str = "real",
        horizonte_min: Optional[float] = None,
        warmup_min: Optional[float] = None,
    ) -> None:
        assert modo in ("markoviano", "real")
        self.env = env
        self.P = params
        self.estrategia = estrategia
        self.rng = rng
        self.stats = recolector
        self.modo = modo
        # Horizonte/warm-up efectivos (permiten horizonte largo de validacion).
        self.horizonte = horizonte_min if horizonte_min is not None else params.horizonte_min
        self.warmup = warmup_min if warmup_min is not None else params.warmup_min

        self.cola: List[Ticket] = []
        self._next_id = 0

        # Pool de conexiones de la API = limite duro C6.
        self.pool = simpy.Resource(env, capacity=params.pool_conexiones)

        # Tecnicos: generalistas en Round Robin; especializados en Skill-Based.
        self.tecnicos: List[Tecnico] = self._crear_tecnicos()

        # Arranque de la generacion de llegadas.
        self.env.process(self._generador_llegadas())

    # ------------------------------------------------------------------ #
    #  Construccion de recursos
    # ------------------------------------------------------------------ #
    def _crear_tecnicos(self) -> List[Tecnico]:
        todas = set(self.P.tipos)
        if self.estrategia.nombre == "skill_based":
            reparto = self.P.habilidades_por_tecnico()
            return [Tecnico(id=i, habilidades=set(reparto[i]))
                    for i in range(self.P.c_tecnicos)]
        # Round Robin / markoviano: tecnicos generalistas (homogeneos).
        return [Tecnico(id=i, habilidades=set(todas))
                for i in range(self.P.c_tecnicos)]

    # ------------------------------------------------------------------ #
    #  Llegadas
    # ------------------------------------------------------------------ #
    def _tasa_llegada(self, t: float) -> float:
        """Tasa instantanea lambda(t) en tickets/min (no estacionaria)."""
        if self.modo == "markoviano":
            return self.P.lambda_valle
        for (ini, fin) in self.P.ventanas_pico:
            if ini <= t < fin:
                return self.P.lambda_pico
        return self.P.lambda_valle

    def _muestrear_tipo(self) -> str:
        return self.rng.choices(list(self.P.tipos), weights=list(self.P.mezcla_tipos))[0]

    def _muestrear_prioridad(self) -> int:
        return self.rng.choices(list(self.P.prioridades),
                                weights=list(self.P.mezcla_prioridades))[0]

    def _muestrear_paciencia(self) -> float:
        p = self.rng.gauss(self.P.paciencia_media_min, self.P.paciencia_desv_min)
        return max(self.P.paciencia_min_min, p)  # Normal truncada inferior

    def _nuevo_ticket(self, reintento_num: int = 0) -> Ticket:
        self._next_id += 1
        return Ticket(
            id=self._next_id,
            tipo=self._muestrear_tipo(),
            prioridad=self._muestrear_prioridad(),
            t_llegada=self.env.now,
            paciencia=self._muestrear_paciencia(),
            reintento_num=reintento_num,
        )

    def _generador_llegadas(self):
        """
        Proceso Poisson. En modo real usa THINNING sobre lambda_pico para
        generar un proceso de Poisson NO homogeneo correcto.
        """
        lam_max = (self.P.lambda_pico if self.modo == "real" else self.P.lambda_valle)
        while True:
            yield self.env.timeout(self.rng.expovariate(lam_max))
            if self.env.now > self.horizonte:
                break
            # Aceptacion/rechazo (thinning) para la tasa no estacionaria.
            if self.rng.random() <= self._tasa_llegada(self.env.now) / lam_max:
                ticket = self._nuevo_ticket()
                self.env.process(self._proceso_llegada(ticket, es_reintento=False))

    def _proceso_llegada(self, ticket: Ticket, es_reintento: bool):
        """Registro/validacion del ticket: ocupa una conexion del pool (C6)."""
        self.stats.registrar_llegada(self.env.now, es_reintento)

        # Limite duro C6: si no hay conexion libre -> rechazo (solo modo real).
        if self.modo == "real" and self.pool.count >= self.pool.capacity:
            ticket.estado = Estado.RECHAZADO
            self.stats.registrar_rechazo(ticket)
            self._actualizar_estado()
            return

        with self.pool.request() as req:
            yield req
            # Tiempo de validacion/registro en la API (segundos -> minutos).
            yield self.env.timeout(self.P.validacion_media_s / 60.0)

        # Encola y, en modo real, arranca el reloj de paciencia (abandono C7).
        ticket.estado = Estado.EN_COLA
        self.cola.append(ticket)
        if self.modo == "real":
            self.env.process(self._vigilar_paciencia(ticket))
        self._actualizar_estado()
        self._despachar()

    # ------------------------------------------------------------------ #
    #  Abandono (paciencia) y reintentos  -- Criterio C7
    # ------------------------------------------------------------------ #
    def _vigilar_paciencia(self, ticket: Ticket):
        yield self.env.timeout(ticket.paciencia)
        if ticket.estado == Estado.EN_COLA and ticket in self.cola:
            self.cola.remove(ticket)
            ticket.estado = Estado.ABANDONADO
            self.stats.registrar_abandono(ticket)
            self._actualizar_estado()
            # Reintento con cierta probabilidad y tope de reintentos.
            if (self.rng.random() < self.P.prob_reintento
                    and ticket.reintento_num < self.P.max_reintentos):
                self.env.process(self._proceso_reintento(ticket))

    def _proceso_reintento(self, ticket_original: Ticket):
        yield self.env.timeout(self.rng.expovariate(1.0 / self.P.reintento_espera_min))
        if self.env.now > self.horizonte:
            return
        nuevo = self._nuevo_ticket(reintento_num=ticket_original.reintento_num + 1)
        nuevo.tipo = ticket_original.tipo
        nuevo.prioridad = ticket_original.prioridad
        self.env.process(self._proceso_llegada(nuevo, es_reintento=True))

    # ------------------------------------------------------------------ #
    #  Despacho (aplica la STRATEGY) y atencion
    # ------------------------------------------------------------------ #
    def _despachar(self) -> None:
        if not self.cola:
            return
        # Orden canonico de cola: prioridad asc (1=critico primero), luego FIFO.
        self.cola.sort(key=lambda t: (t.prioridad, t.t_llegada))
        asignaciones = self.estrategia.asignar(self.cola, self.tecnicos)
        for ticket, tecnico in asignaciones:
            if ticket in self.cola and tecnico.disponible:
                self.cola.remove(ticket)
                self.env.process(self._atender(ticket, tecnico))

    def _tiempo_servicio(self, ticket: Ticket, tecnico: Tecnico) -> float:
        if self.modo == "markoviano":
            return self.rng.expovariate(self.P.mu)  # media = 15 min (M/M/c)
        # Lognormal con la MISMA media base (15) y cola larga.
        media = self.P.tiempo_servicio_min
        # Supuesto de politica: el especialista (Skill-Based) resuelve su
        # dominio mas rapido. Round Robin (generalista) usa el tiempo base.
        if self.estrategia.nombre == "skill_based" and tecnico.puede_atender(ticket.tipo):
            media *= self.P.servicio_skill_factor
        sigma = self.P.servicio_lognormal_sigma
        mu_log = math.log(media) - 0.5 * sigma ** 2
        return self.rng.lognormvariate(mu_log, sigma)

    def _atender(self, ticket: Ticket, tecnico: Tecnico):
        tecnico.disponible = False
        ticket.estado = Estado.EN_ATENCION
        ticket.t_inicio_atencion = self.env.now
        ticket.tecnico_id = tecnico.id
        self._actualizar_estado()

        dur = self._tiempo_servicio(ticket, tecnico)
        yield self.env.timeout(dur)

        ticket.t_fin = self.env.now
        ticket.estado = Estado.RESUELTO
        tecnico.disponible = True
        tecnico.tickets_atendidos += 1
        tecnico.tiempo_ocupado += dur

        # Minutos-tecnico ocupados DENTRO de la ventana de medicion (utilizacion).
        ini = max(ticket.t_inicio_atencion, self.warmup)
        fin = min(ticket.t_fin, self.horizonte)
        if fin > ini:
            self.stats.registrar_ocupacion(fin - ini)

        self.stats.registrar_resuelto(ticket)
        self._actualizar_estado()
        self._despachar()

    # ------------------------------------------------------------------ #
    #  Estado del sistema (para integrar L(t) y Lq(t))
    # ------------------------------------------------------------------ #
    def _actualizar_estado(self) -> None:
        en_cola = len(self.cola)
        ocupados = sum(1 for t in self.tecnicos if not t.disponible)
        self.stats.set_estado_sistema(self.env.now, en_cola + ocupados, en_cola)

    def finalizar(self) -> None:
        """Cierra las areas de L(t)/Lq(t) al final del horizonte."""
        self.stats.set_estado_sistema(self.horizonte,
                                      self.stats._L_actual, self.stats._Lq_actual)
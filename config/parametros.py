# archivo: config/parametros.py
"""
================================================================================
 OptiSupport  ·  Parametros canonicos del sistema  (FUENTE UNICA DE VERDAD)
================================================================================
Modelos y Simulacion (2026-2) - I.U. Pascual Bravo - Grupo 3

Este archivo resuelve la DEUDA TECNICA #1 de la Entrega 1:
    "Corregir la inconsistencia matematica de tasas: 0.2 tickets/min
     (5 min/ticket) vs. 15 min/ticket declarados, que volvia inestable
     el sistema base con rho = 1.875."

Decision de subsanacion:
    - Se CONSERVA el tiempo de servicio documentado de 15 min/ticket
      (mu = 1/15 = 0.066667 tickets/min), que era el valor conceptualmente
      correcto, y se ELIMINA la tasa espuria de 0.2 tickets/min.
    - Como con c = 4 el sistema es inestable (rho = 1.875 > 1), se recalibra
      el numero de servidores base a c = 9, con lo que rho = 0.833 < 0.85,
      cumpliendo el objetivo de utilizacion del enunciado.

TANTO la API como la simulacion importan `P` desde aqui, de modo que es
imposible que diverjan los parametros entre codigo y documento.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Parametros:
    # ----------------------------------------------------------------------
    # 1. TASAS BASE DEL SUBSISTEMA DE ATENCION  (coherentes y estables)
    # ----------------------------------------------------------------------
    # Tasa media de llegada en demanda promedio (valle).
    lambda_valle: float = 0.5           # tickets / minuto  (= 30 tickets/hora)
    # Tasa de llegada en pico (escenario de estres, Entrega 1).
    lambda_pico: float = 1.5            # tickets / minuto  (= 90 tickets/hora)

    # Tiempo medio de servicio por ticket. VALOR CANONICO: 15 min/ticket.
    tiempo_servicio_min: float = 15.0   # minutos / ticket
    # mu se deriva SIEMPRE de tiempo_servicio_min -> imposible desincronizar.

    # Numero de tecnicos (servidores c). Recalibrado de 4 -> 9 para estabilidad.
    c_tecnicos: int = 9

    # ----------------------------------------------------------------------
    # 2. LIMITE FISICO DURO  (Criterio C6)
    # ----------------------------------------------------------------------
    # Pool de conexiones de la API. Es un limite de DISENO, no de la BD.
    pool_conexiones: int = 50           # maximo de conexiones concurrentes

    # ----------------------------------------------------------------------
    # 3. COMPORTAMIENTO DE AGENTES  (Criterio C7)
    # ----------------------------------------------------------------------
    # Paciencia del usuario antes de abandonar (Normal truncada).
    paciencia_media_min: float = 30.0   # minutos
    paciencia_desv_min: float = 5.0     # minutos
    paciencia_min_min: float = 5.0      # truncamiento inferior

    # Reintentos tras abandono.
    prob_reintento: float = 0.40        # probabilidad de reintentar al abandonar
    max_reintentos: int = 2             # reintentos maximos por usuario
    reintento_espera_min: float = 10.0  # media de la espera antes de reintentar (Exp)

    # ----------------------------------------------------------------------
    # 4. VARIABILIDAD DEL SERVICIO  (modo "real" no markoviano)
    # ----------------------------------------------------------------------
    # En modo markoviano el servicio es Exponencial(media=15) -> compara con M/M/c.
    # En modo real el servicio es Lognormal con la MISMA media de 15 min y cola larga.
    servicio_lognormal_sigma: float = 0.5   # sigma del log (cola larga realista)

    # SUPUESTO DE POLITICA (no modifica el valor canonico mu de 15 min):
    # en Skill-Based Routing el ticket se asigna a un ESPECIALISTA de su dominio,
    # que lo resuelve mas rapido por experiencia. Es el fundamento teorico del
    # enrutamiento por habilidades (Garnett & Mandelbaum, 2000; Wallace & Whitt,
    # 2005). Round Robin (generalistas) usa el tiempo base de 15 min.
    servicio_skill_factor: float = 0.80     # especialista: 15 min -> 12 min (dominio)

    # Tiempo de validacion/registro en la API (uso del pool de conexiones C6).
    validacion_media_s: float = 0.8     # segundos (etapa que ocupa una conexion)

    # ----------------------------------------------------------------------
    # 5. TIPOS DE TICKET, PRIORIDADES Y HABILIDADES DE LOS TECNICOS
    # ----------------------------------------------------------------------
    # Tipos de ticket (Entrega 1: Redes / BD / Infraestructura).
    tipos: Tuple[str, ...] = ("REDES", "BD", "INFRA")
    # Mezcla de llegada por tipo (debe sumar 1.0).
    mezcla_tipos: Tuple[float, ...] = (0.40, 0.30, 0.30)

    # Prioridades: 1 = critico, 2 = alto, 3 = normal. Mezcla de llegada.
    prioridades: Tuple[int, ...] = (1, 2, 3)
    mezcla_prioridades: Tuple[float, ...] = (0.15, 0.35, 0.50)

    # ----------------------------------------------------------------------
    # 6. ACUERDOS DE NIVEL DE SERVICIO  (SLA / umbrales)
    # ----------------------------------------------------------------------
    # SLA de negocio (modelo DES, extremo a extremo, en minutos).
    sla_p95_atencion_min: float = 45.0  # p95 del tiempo total de atencion
    sla_abandono_max: float = 0.03      # fraccion maxima de abandono (3%)
    sla_utilizacion_min: float = 0.70   # banda objetivo de utilizacion ...
    sla_utilizacion_max: float = 0.85   # ... del cuello de botella (tecnicos)

    # SLA de la capa tecnica (API, telemetria, en segundos).
    sla_p95_latencia_api_s: float = 2.0  # p95 de latencia HTTP de la API

    # ----------------------------------------------------------------------
    # 7. DISENO EXPERIMENTAL  (reproducibilidad)
    # ----------------------------------------------------------------------
    horizonte_min: float = 480.0        # jornada operativa 08:00-16:00 (8 h)
    warmup_min: float = 60.0            # periodo de calentamiento descartado
    n_replicas: int = 30                # replicas independientes (N >= 30)
    semilla_base: int = 42              # semillas usadas: 42 .. 42+n_replicas-1

    # Horizonte largo SOLO para el contraste analitico M/M/c (regimen
    # estacionario): un horizonte corto sesga Lq/Wq a la baja por el
    # truncamiento de fin de jornada. El estudio operativo usa la jornada real.
    horizonte_validacion_min: float = 3000.0
    warmup_validacion_min: float = 300.0

    # Ventanas de pico dentro de la jornada (minuto_inicio, minuto_fin).
    # 08:00 = 0 min. Rafagas cortas (no sostenidas): c=9 se dimensiono para el
    # valle, por lo que un pico a 1.5 tickets/min (2.5x la capacidad) solo es
    # absorbible si dura poco y el sistema se recupera en el valle siguiente.
    ventanas_pico: Tuple[Tuple[float, float], ...] = (
        (150.0, 175.0),   # 10:30 - 10:55  (rafaga de media manana)
        (360.0, 385.0),   # 14:00 - 14:25  (rafaga de tarde)
    )

    # ----------------------------------------------------------------------
    # Propiedades derivadas  (NUNCA se escriben a mano, siempre se calculan)
    # ----------------------------------------------------------------------
    @property
    def mu(self) -> float:
        """Tasa de servicio por tecnico (tickets/min). Deriva de 15 min/ticket."""
        return 1.0 / self.tiempo_servicio_min

    @property
    def rho_base(self) -> float:
        """Utilizacion del subsistema de tecnicos en demanda promedio."""
        return self.lambda_valle / (self.c_tecnicos * self.mu)

    @property
    def rho_c4(self) -> float:
        """Utilizacion que tendria la config. inestable de la Entrega 1 (c=4)."""
        return self.lambda_valle / (4 * self.mu)

    @property
    def semillas(self) -> List[int]:
        return [self.semilla_base + i for i in range(self.n_replicas)]

    def habilidades_por_tecnico(self) -> List[set]:
        """
        Reparto de habilidades para la politica Skill-Based Routing.
        En la politica base (Round Robin) los tecnicos son generalistas
        (atienden los 3 tipos); aqui se define el reparto especializado que
        usa la politica alternativa para demostrar el patron Strategy.
        """
        n = self.c_tecnicos
        tipos = list(self.tipos)
        hab: List[set] = []
        for i in range(n):
            principal = tipos[i % len(tipos)]
            secundario = tipos[(i + 1) % len(tipos)]  # respaldo cruzado
            hab.append({principal, secundario})
        return hab

    def resumen(self) -> Dict:
        """Diccionario serializable con los parametros clave (para el JSON)."""
        return {
            "lambda_valle_tickets_min": self.lambda_valle,
            "lambda_pico_tickets_min": self.lambda_pico,
            "tiempo_servicio_min": self.tiempo_servicio_min,
            "mu_tickets_min": round(self.mu, 6),
            "c_tecnicos": self.c_tecnicos,
            "rho_base": round(self.rho_base, 4),
            "rho_config_entrega1_c4": round(self.rho_c4, 4),
            "pool_conexiones_C6": self.pool_conexiones,
            "paciencia_media_min": self.paciencia_media_min,
            "prob_reintento": self.prob_reintento,
            "max_reintentos": self.max_reintentos,
            "horizonte_min": self.horizonte_min,
            "warmup_min": self.warmup_min,
            "n_replicas": self.n_replicas,
            "semillas": f"{self.semilla_base}..{self.semilla_base + self.n_replicas - 1}",
            "sla_p95_atencion_min": self.sla_p95_atencion_min,
            "sla_abandono_max": self.sla_abandono_max,
            "sla_utilizacion_objetivo": [self.sla_utilizacion_min, self.sla_utilizacion_max],
        }


# Instancia unica importada por TODO el proyecto.
P = Parametros()


if __name__ == "__main__":
    import json
    print(json.dumps(P.resumen(), indent=2, ensure_ascii=False))
    print(f"\n  mu           = 1/{P.tiempo_servicio_min} = {P.mu:.6f} tickets/min")
    print(f"  rho (c=4)    = {P.rho_c4:.4f}   -> INESTABLE (Entrega 1)")
    print(f"  rho (c={P.c_tecnicos})    = {P.rho_base:.4f}   -> ESTABLE  (Entrega Final)")
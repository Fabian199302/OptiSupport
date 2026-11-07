# archivo: sistema_real/schemas.py
"""Esquemas Pydantic de entrada/salida de la API."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
from config.parametros import P  # noqa: E402


class TicketIn(BaseModel):
    """Cuerpo para crear un ticket (simula una llegada al sistema)."""
    tipo: str = Field(..., description="Tipo de ticket: REDES, BD o INFRA")
    prioridad: int = Field(3, ge=1, le=3, description="1=critico, 2=alto, 3=normal")

    @field_validator("tipo")
    @classmethod
    def _tipo_valido(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in P.tipos:
            raise ValueError(f"tipo debe ser uno de {P.tipos}")
        return v


class TicketOut(BaseModel):
    id: int
    tipo: str
    prioridad: int
    estado: str
    creado_en: Optional[str] = None
    resuelto_en: Optional[str] = None


class EstadoSistema(BaseModel):
    tickets_total: int
    tickets_por_estado: dict
    pool: dict
    tecnicos: int
    parametros_clave: dict
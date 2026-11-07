# archivo: sistema_real/models.py
"""Modelos ORM (SQLAlchemy) de la API OptiSupport."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, DateTime, Integer, String

from .database import Base


class TicketDB(Base):
    """
    Persistencia de un ticket de soporte. Refleja la entidad `Ticket` del
    modelo DES (tipo, prioridad, estado y marcas temporales).
    """
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tipo = Column(String(16), nullable=False)        # REDES / BD / INFRA
    prioridad = Column(Integer, nullable=False)       # 1=critico, 2=alto, 3=normal
    estado = Column(String(16), nullable=False, default="EN_COLA")
    creado_en = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    resuelto_en = Column(DateTime, nullable=True)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "prioridad": self.prioridad,
            "estado": self.estado,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
            "resuelto_en": self.resuelto_en.isoformat() if self.resuelto_en else None,
        }
# archivo: sistema_real/main.py
"""
API REST de OptiSupport (FastAPI).

Expone el "sistema real" contenerizado: recibe tickets (simula llegadas), los
persiste, permite consultar su estado y el estado del sistema, y captura
TELEMETRIA de cada peticion en datos/telemetry_log.csv.

Comparte los parametros (lambda, mu, c, pool) con la simulacion a traves de
`config.parametros`, garantizando coherencia entre codigo y documento.

Endpoints principales:
    GET  /health              salud del servicio
    GET  /parametros          parametros canonicos (mismos que la simulacion)
    POST /tickets             crea un ticket (llegada)
    GET  /tickets             lista tickets
    GET  /tickets/{id}        consulta un ticket
    POST /tickets/{id}/resolver   marca un ticket como resuelto
    GET  /estado              estado del sistema + pool (C6)
    GET  /metricas            resumen de la telemetria capturada
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config.parametros import P  # noqa: E402
from sistema_real import telemetria  # noqa: E402
from sistema_real.database import estado_pool, get_db, init_db  # noqa: E402
from sistema_real.models import TicketDB  # noqa: E402
from sistema_real.schemas import EstadoSistema, TicketIn, TicketOut  # noqa: E402

app = FastAPI(
    title="OptiSupport API",
    version="1.0.0",
    description="Sistema real de soporte tecnico — Grupo 3, Modelos y Simulacion 2026-2",
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------- #
#  Middleware de TELEMETRIA: cronometra y registra cada peticion.
# --------------------------------------------------------------------- #
@app.middleware("http")
async def telemetria_middleware(request: Request, call_next):
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
        status = respuesta.status_code
    except Exception:
        status = 500
        raise
    finally:
        tiempo_ms = (time.perf_counter() - inicio) * 1000.0
        pool = estado_pool()
        try:
            db = next(get_db())
            abiertos = db.query(func.count(TicketDB.id)).filter(
                TicketDB.estado.in_(["EN_COLA", "EN_ATENCION"])
            ).scalar() or 0
            db.close()
        except Exception:
            abiertos = 0
        telemetria.registrar(
            metodo=request.method, ruta=request.url.path, status=status,
            tiempo_ms=tiempo_ms, pool_en_uso=pool["conexiones_en_uso"],
            pool_limite=pool["limite_C6"], tickets_abiertos=int(abiertos),
        )
    return respuesta


# --------------------------------------------------------------------- #
#  Endpoints
# --------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "servicio": "optisupport-api"}


@app.get("/parametros")
def parametros() -> dict:
    """Parametros canonicos — IDENTICOS a los de la simulacion."""
    return P.resumen()


@app.post("/tickets", response_model=TicketOut, status_code=201)
def crear_ticket(ticket: TicketIn, db: Session = Depends(get_db)) -> TicketOut:
    """Recibe un ticket (simula una llegada al sistema)."""
    registro = TicketDB(tipo=ticket.tipo, prioridad=ticket.prioridad, estado="EN_COLA")
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return TicketOut(**registro.a_dict())


@app.get("/tickets", response_model=list[TicketOut])
def listar_tickets(limite: int = 50, db: Session = Depends(get_db)) -> list[TicketOut]:
    filas = db.query(TicketDB).order_by(TicketDB.id.desc()).limit(limite).all()
    return [TicketOut(**f.a_dict()) for f in filas]


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def consultar_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    f = db.get(TicketDB, ticket_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return TicketOut(**f.a_dict())


@app.post("/tickets/{ticket_id}/resolver", response_model=TicketOut)
def resolver_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    import datetime as dt
    f = db.get(TicketDB, ticket_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    f.estado = "RESUELTO"
    f.resuelto_en = dt.datetime.utcnow()
    db.commit()
    db.refresh(f)
    return TicketOut(**f.a_dict())


@app.get("/estado", response_model=EstadoSistema)
def estado(db: Session = Depends(get_db)) -> EstadoSistema:
    total = db.query(func.count(TicketDB.id)).scalar() or 0
    por_estado = dict(
        db.query(TicketDB.estado, func.count(TicketDB.id)).group_by(TicketDB.estado).all()
    )
    return EstadoSistema(
        tickets_total=int(total),
        tickets_por_estado={k: int(v) for k, v in por_estado.items()},
        pool=estado_pool(),
        tecnicos=P.c_tecnicos,
        parametros_clave={
            "lambda_valle": P.lambda_valle,
            "mu": round(P.mu, 5),
            "c": P.c_tecnicos,
            "rho_base": round(P.rho_base, 4),
        },
    )


@app.get("/metricas")
def metricas() -> dict:
    return {"telemetria": telemetria.resumen(), "pool": estado_pool()}


@app.get("/")
def raiz() -> dict:
    return {
        "servicio": "OptiSupport API",
        "docs": "/docs",
        "endpoints": ["/health", "/parametros", "/tickets", "/estado", "/metricas"],
    }
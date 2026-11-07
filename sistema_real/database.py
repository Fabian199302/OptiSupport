# archivo: sistema_real/database.py
"""
Capa de persistencia de la API OptiSupport.

Punto CLAVE para el Criterio C6 (limite fisico duro):
el pool de conexiones de SQLAlchemy se configura con `pool_size =
P.pool_conexiones` (50) y `max_overflow = 0`, de modo que el numero MAXIMO de
conexiones concurrentes a la base de datos es EXACTAMENTE 50. Al superarlo, las
peticiones esperan hasta `pool_timeout` y, si no obtienen conexion, la API
responde 503 (saturacion del pool). Es el mismo valor que consume la
simulacion desde `config.parametros`.

La URL de conexion se toma de DATABASE_URL:
  - En Docker (docker-compose) apunta a PostgreSQL.
  - Si no se define, cae a un SQLite local para pruebas rapidas sin contenedor.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Importa los parametros canonicos compartidos (misma fuente que la simulacion).
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
from config.parametros import P  # noqa: E402

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./optisupport_local.db",  # fallback local sin Docker
)

_es_sqlite = DATABASE_URL.startswith("sqlite")

if _es_sqlite:
    # SQLite no usa QueuePool con pool_size; se deja constancia del limite C6
    # a nivel aplicativo (ver middleware/semaforo en main.py).
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    # PostgreSQL: LIMITE DURO C6 = pool_size + max_overflow = 50 + 0 = 50.
    engine = create_engine(
        DATABASE_URL,
        pool_size=P.pool_conexiones,   # 50 conexiones (C6)
        max_overflow=0,                # sin desbordamiento -> tope duro
        pool_timeout=5,                # s de espera antes de 503
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """Dependencia FastAPI: entrega una sesion y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def estado_pool() -> dict:
    """Instrumentacion del pool para telemetria y endpoint /estado (C6)."""
    pool = engine.pool
    try:
        en_uso = pool.checkedout()
    except Exception:
        en_uso = 0
    tamano = getattr(pool, "size", lambda: P.pool_conexiones)()
    return {
        "limite_C6": P.pool_conexiones,
        "pool_size": tamano or P.pool_conexiones,
        "conexiones_en_uso": en_uso,
        "conexiones_libres": max((tamano or P.pool_conexiones) - en_uso, 0),
        "backend": "sqlite" if _es_sqlite else "postgresql",
    }


def init_db(reintentos: int = 10, espera_s: float = 2.0) -> None:
    """
    Crea las tablas. Reintenta la conexion porque, en docker-compose, la API
    puede arrancar antes de que PostgreSQL este listo.
    """
    from . import models  # noqa: F401  (registra los modelos en Base)

    ultimo_error = None
    for intento in range(1, reintentos + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print(f"[DB] Esquema listo en {DATABASE_URL.split('@')[-1]}")
            return
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
            print(f"[DB] Intento {intento}/{reintentos} fallo: {exc}. "
                  f"Reintentando en {espera_s}s ...")
            time.sleep(espera_s)
    raise RuntimeError(f"No se pudo inicializar la base de datos: {ultimo_error}")
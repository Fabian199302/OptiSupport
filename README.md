# archivo: README.md

# OptiSupport — Gemelo digital de una mesa de soporte técnico

**Modelos y Simulación (2026-2) · I.U. Pascual Bravo · Grupo 3**

Simulación de eventos discretos (DES) de un sistema de asignación de tickets de
soporte, con API REST real contenerizada, telemetría, modelo SimPy con dos
políticas de asignación (patrón Strategy) y validación analítica M/M/c.

> **Subsanación clave de la Entrega 1:** se corrigió la inconsistencia de tasas
> (μ = 1/15 = 0.0667 tickets/min como valor canónico) y se recalibró el sistema
> a **c = 9 técnicos**, logrando **ρ = 0.833 (estable, < 0.85)** en vez del
> ρ = 1.875 inestable con c = 4. API y simulación comparten los parámetros desde
> `config/parametros.py` (fuente única de verdad).

---

## Requisitos

- **Docker** y **Docker Compose** (para la API + base de datos).
- **Python 3.11+** (para la simulación y el análisis).

## 1) Levantar el sistema real (API + base de datos)

Un solo comando levanta los **dos servicios** (FastAPI + PostgreSQL):

```bash
docker compose up --build -d
```

- API disponible en **http://localhost:8000** (documentación interactiva en `/docs`).
- Endpoints: `GET /health`, `GET /parametros`, `POST /tickets`, `GET /tickets/{id}`,
  `GET /estado`, `GET /metricas`.
- Límite duro **C6**: el pool de conexiones está fijado a **50** (`pool_size=50,
max_overflow=0`) en `sistema_real/database.py`.

Generar **telemetría real** (latencias + uso del pool) en `datos/telemetry_log.csv`:

```bash
# con la API levantada
pip install requests
python sistema_real/generar_carga.py --n 300 --acelerado
```

Comprobar estado y métricas:

```bash
curl http://localhost:8000/estado
curl http://localhost:8000/metricas
```

Detener:

```bash
docker compose down          # conserva el volumen de datos
docker compose down -v       # borra también la base de datos
```

## 2) Ejecutar la simulación SimPy (reproduce las tablas del informe)

```bash
pip install -r requirements.txt     # simpy, numpy, matplotlib
python simulacion/main.py
```

Genera:

- `simulacion/resultados_simulacion.json` — KPIs agregados (media ± IC95, p95/p99)
  de los 3 escenarios con 30 réplicas (semillas 42..71).
- `docs/figuras/politicas_kpis.png` — comparación de políticas con umbrales SLA.
- `docs/figuras/perfil_llegadas.png` — perfil de llegadas no estacionario.

## 3) Contraste analítico M/M/c vs. SimPy

```bash
python analisis/contraste_mmc.py
```

Genera `docs/tabla_contraste_mmc.md` (tabla de validación + dimensionamiento
Erlang C) y `docs/figuras/contraste_mmc.png`. La simulación markoviana reproduce
el modelo M/M/9 analítico con **error < 1.2 %**.

## Reproducir TODO de una vez

```bash
docker compose up --build -d                 # (1) sistema real
pip install -r requirements.txt
python simulacion/main.py                     # (2) simulación
python analisis/contraste_mmc.py             # (3) contraste
```

---

## Estructura del repositorio

```
OptiSupport/
├── docker-compose.yml          # 2 servicios: api (FastAPI) + db (PostgreSQL)
├── requirements.txt            # dependencias de simulación y análisis
├── config/
│   └── parametros.py           # FUENTE ÚNICA DE VERDAD (λ, μ, c, pool=50)
├── sistema_real/               # API REST + persistencia + telemetría
│   ├── main.py                 # endpoints + middleware de telemetría
│   ├── database.py             # pool de 50 conexiones (C6)
│   ├── models.py  schemas.py   # ORM + validación
│   ├── telemetria.py           # registro a datos/telemetry_log.csv
│   ├── generar_carga.py        # generador de carga (telemetría real)
│   └── Dockerfile
├── simulacion/                 # modelo SimPy completo
│   ├── entidades.py            # Ticket, Tecnico
│   ├── estrategias.py          # Strategy: RoundRobin + SkillBased
│   ├── estadisticas.py         # KPIs, IC95, percentiles
│   ├── modelo.py               # SimuladorOrquestador (llegadas, abandono, reintentos)
│   └── main.py                 # corre réplicas -> resultados_simulacion.json
├── analisis/
│   └── contraste_mmc.py        # Erlang C vs SimPy -> tabla Markdown
├── datos/
│   └── telemetry_log.csv       # telemetría capturada por la API
└── docs/
    ├── INFORME_FINAL.md        # informe (6 secciones oficiales)
    ├── tabla_contraste_mmc.md  # tabla de validación generada
    └── figuras/                # gráficas generadas por la simulación
```

## Parámetros del modelo (coherentes entre API y simulación)

| Parámetro               | Valor                                        | Nota                      |
| :---------------------- | :------------------------------------------- | :------------------------ |
| λ (valle / pico)        | 0.5 / 1.5 tickets/min                        | llegadas no estacionarias |
| Tiempo de servicio      | 15 min (μ = 0.0667/min)                      | valor canónico corregido  |
| Técnicos (c)            | 9                                            | ρ = 0.833 (estable)       |
| Pool de conexiones (C6) | 50                                           | límite físico duro        |
| Paciencia (abandono)    | Normal(30, 5) min                            | reintento p=0.40, máx. 2  |
| SLA                     | p95 < 45 min · abandono < 3 % · util 70–85 % | —                         |

Ver el informe completo en [`docs/INFORME_FINAL.md`](docs/INFORME_FINAL.md).

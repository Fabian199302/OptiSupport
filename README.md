# OptiSupport — Gemelo Digital de una Mesa de Soporte Técnico

> Simulación de eventos discretos (**DES**) de un sistema de asignación de tickets de soporte, con una API REST real contenerizada, telemetría integrada, un modelo estocástico en **SimPy** con dos políticas de asignación (patrón *Strategy*) y validación analítica mediante colas **M/M/c**.

---

### 🏛️ Contexto Académico e Integrantes
- **Institución:** I.U. Pascual Bravo — Modelos y Simulación (2026-2)
- **Grupo de Trabajo:** Grupo 3
- **Integrantes:** 
  * **Fabian Eliecer Montoya**
  * **Mateo Corrales**
  * **Stefanny Higuita**

> 💡 **Subsanación clave de la Entrega 1:** Se corrigió la inconsistencia de tasas ($\mu = 1/15 = 0.0667$ tickets/min como valor canónico) y se recalibró el sistema a **$c = 9$ técnicos**, logrando una intensidad de tráfico estable de $\rho = 0.833$ ($< 0.85$) en lugar del $\rho = 1.875$ inestable obtenido previamente con $c = 4$. La API y la simulación comparten de forma estricta los mismos parámetros desde `config/parametros.py` (Fuente Única de Verdad).

---

## 📋 Tabla de Contenidos
1. [Requisitos Previos](#requisitos-previos)
2. [Paso 1: Levantar el Sistema Real (API + Base de Datos)](#1-levantar-el-sistema-real-api--base-de-datos)
3. [Paso 2: Ejecutar la Simulación SimPy](#2-ejecutar-la-simulación-simpy)
4. [Paso 3: Contraste Analítico M/M/c vs. SimPy](#3-contraste-analítico-mmc-vs-simpy)
5. [Paso 4: Análisis de sensibilidad](#4-análisis-de-sensibilidad)
6. [Ejecución Rápida (Todo en uno)](#-ejecución-rápida-todo-en-uno)
7. [Parámetros del Modelo](#parámetros-del-modelo-coherentes-entre-api-y-simulación)
8. [Estructura del Repositorio](#estructura-del-repositorio)

---

## Requisitos Previos

Asegúrate de tener instalado en tu computadora lo siguiente antes de comenzar:
- **[Git](https://git-scm.com/)** (para clonar el repositorio).
- **[Docker y Docker Compose](https://www.docker.com/)** (para levantar la base de datos PostgreSQL y el servicio de la API).
- **[Python](https://www.python.org/) (Versión 3.11 o superior)** (para la ejecución de los scripts de simulación y análisis).

---

## Guía de Instalación y Ejecución Paso a Paso

### Clonar el repositorio
Si aún no lo has descargado en tu máquina local, abre tu terminal y ejecuta:

```bash
git clone [https://github.com/Fabian199302/OptiSupport.git](https://github.com/Fabian199302/OptiSupport.git)
cd OptiSupport
```

## 1) Levantar el Sistema Real (API + Base de Datos)

Un solo comando mediante Docker Compose se encarga de poner en marcha los dos servicios necesarios (FastAPI y PostgreSQL):

```bash
docker compose up --build -d
```

- API Interactiva: Disponible en http://localhost:8000 (puedes probar la documentación visual en /docs).

- Endpoints principales: GET /health, GET /parametros, POST /tickets, GET /tickets/{id}, GET /estado, GET /metricas.

- Límite de Conexiones (C6): El pool de conexiones está fijado estrictamente a 50 (pool_size=50, max_overflow=0) en sistema_real/database.py.

Generar telemetría real

Para simular tráfico y registrar latencias y uso del pool de conexiones en datos/telemetry_log.csv:

```bash
pip install requests
python sistema_real/generar_carga.py --n 300 --acelerado
```

Comprobar estado y métricas vía terminal:

```bash
curl http://localhost:8000/estado
curl http://localhost:8000/metricas
```

Para detener los servicios cuando termines:

```bash
docker compose down (Conserva los datos de la base de datos).
docker compose down -v (Detiene los servicios y borra los datos de la base de datos).
```

## 2) Ejecutar la Simulación SimPy

Para correr los modelos de eventos discretos que replican los escenarios del informe:

```bash
1. Instala las dependencias necesarias de Python: 
pip install -r requirements.txt

2. Ejecuta el orquestador de simulación:
python simulacion/main.py
```

Archivos generados automáticamente:

- simulacion/resultados_simulacion.json — KPIs agregados (medias con IC del 95%, percentiles p95/p99) evaluados en 3 escenarios con 30 réplicas (semillas de la 42 a la 71).

- Resumen en consola en tablas Markdown: validación M/M/c, comparación de políticas, cumplimiento de SLA y totales de tickets.

- docs/figuras/politicas_kpis.png — Comparativa de políticas de asignación frente a umbrales de SLA.

- docs/figuras/perfil_llegadas.png — Visualización del perfil de llegadas no estacionario.

## 3) Contraste Analítico M/M/c vs. SimPy

Para validar formalmente el comportamiento estocástico de la simulación frente a los modelos analíticos de colas (Erlang C):

```bash
python analisis/contraste_mmc.py
```

Salidas: Genera el reporte de validación en docs/tabla_contraste_mmc.md y la gráfica comparativa en docs/figuras/contraste_mmc.png.
Nota: La simulación markoviana desarrollada reproduce con éxito el modelo analítico M/M/9 con un error menor al 1.2%.

## 4) Análisis de sensibilidad

Para analizar el efecto del factor de servicio especialista, el número de técnicos y el límite del pool C6:

```bash
python analisis/sensibilidad.py
```

El script ejecuta 30 réplicas por escenario, usando las semillas configuradas en el modelo, e imprime tablas Markdown con medias, IC 95 %, percentiles y rechazos.

## ⚡ Ejecución Rápida (Todo en uno)

```bash
# 1. Levantar contenedores del sistema real
docker compose up --build -d

# 2. Instalar dependencias y correr la simulación
pip install -r requirements.txt
python simulacion/main.py

# 3. Ejecutar contraste analítico
python analisis/contraste_mmc.py

# 4. Ejecutar análisis de sensibilidad
python analisis/sensibilidad.py

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
│   ├── contraste_mmc.py        # Erlang C vs SimPy -> tabla Markdown
│   └── sensibilidad.py         # Analisis de sensibilidad del modelo DES
├── datos/
│   └── telemetry_log.csv       # telemetría capturada por la API
└── docs/
    ├── INFORME_FINAL.md        # informe (6 secciones oficiales)
    ├── tabla_contraste_mmc.md  # tabla de validación generada
    └── figuras/                # gráficas generadas por la simulación
```

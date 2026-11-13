# archivo: docs/INFORME_FINAL.md

# Informe Final — OptiSupport (Asignación de tareas de soporte técnico)

- **Curso:** Modelos y Simulación (2026-2) — I.U. Pascual Bravo
- **Grupo:** Grupo 3
- **Repositorio:** https://github.com/Fabian199302/OptiSupport
- **Comando de despliegue API:** `docker compose up --build -d`
- **Comando de ejecución SimPy:** `python simulacion/main.py`
- **Comando de contraste M/M/c:** `python analisis/contraste_mmc.py`

| Integrante | Correo institucional | Rol y módulos |
|---|---|---|
| Yulisa Stefanny Higuita Rodríguez | yulisa.higuita602@pascualbravo.edu.co | Modelado DES / SimPy<br>`simulacion/` |
| Fabián Eliécer Montoya | f.montoya@pascualbravo.edu.co | Infraestructura / API / Telemetría<br>`sistema_real/`, `docker-compose.yml` |
| Mateo Corrales Vinasco | mateo.corrales571@pascualbravo.edu.co | Análisis estadístico / Contraste M/M/c<br>`analisis/`, `docs/` |

---

## 1. Resumen Ejecutivo

OptiSupport es un gemelo digital de una mesa de soporte técnico donde llegan tickets no estacionarios que se validan, clasifican y asignan a técnicos finitos bajo reglas de prioridad, paciencia (abandono) y SLA. El problema de ingeniería es decidir **qué política de asignación y qué dimensionamiento** de técnicos minimizan el tiempo de atención y el abandono sin sobredimensionar el personal. Se compararon dos políticas con el patrón Strategy —**Round Robin** (política actual, técnicos generalistas) y **Skill-Based Routing** (alternativa, especialistas con balanceo de carga)— sobre 30 réplicas de una jornada de 8 h. La política Skill-Based **reduce el abandono del 13.7 % al 5.4 % (−61 %)**, baja el p95 del tiempo de atención de 44.1 a 37.7 min y sitúa la utilización del cuello de botella en 77.7 % (dentro de la banda 70–85 %), frente al 88.1 % de Round Robin. **Recomendación final:** desplegar Skill-Based Routing y reforzar con 1–2 técnicos durante las dos ráfagas pico; es la única configuración que mantiene el p95 bajo el SLA de 45 min y acerca el abandono al umbral del 3 %.

## 2. Contexto del Sistema y Subsanación de la Entrega 1

### 2.1 Dinámica del Sistema (Qué fluye, qué espera, qué se satura)

- **Entidades que fluyen:** _tickets_ de soporte con atributos `tipo` (REDES / BD / INFRA), `prioridad` (1 = crítico, 2 = alto, 3 = normal), marca de llegada y tiempo de paciencia individual. La mezcla de llegada es 40/30/30 por tipo y 15/35/50 por prioridad.
- **Recursos y colas de contención:** **9 técnicos** (recurso finito, `simpy`) atienden una cola única ordenada por _prioridad y luego FIFO_. En Round Robin los técnicos son generalistas; en Skill-Based están especializados y se enruta al compatible de **menor carga**. La disciplina es no apropiativa.
- **Límite físico duro (C6) y comportamiento de agentes (C7):** el **pool de 50 conexiones** de la API (`pool_size=50, max_overflow=0`) es el tope físico modelado tanto en el código real (`sistema_real/database.py`) como en la simulación (`simpy.Resource(capacity=50)`). El usuario abandona si su espera supera su paciencia `~ Normal(30, 5)` truncada en 5 min (C7), y reintenta con probabilidad 0.40 hasta 2 veces.

### 2.2 Tabla de Subsanación de la Entrega Parcial 1

| Problema detectado | Corrección y ubicación |
|---|---|
| Tasas inconsistentes: servicio de 15 min/ticket frente a 0.2 tickets/min, con ρ=1.875. | Se establece μ = 1/15 = 0.0667 tickets/min como tasa única, derivada de `tiempo_servicio_min`.<br>**Archivo:** `config/parametros.py` |
| Sistema inestable con c=4 técnicos (ρ=1.875). | Se calibra el sistema con c=9, para obtener ρ=0.833.<br>**Archivo:** `config/parametros.py` (`c_tecnicos`, `rho_base`) |
| Repositorio inicialmente vacío. | Se implementan API FastAPI, PostgreSQL, telemetría, simulación SimPy y contraste M/M/c.<br>**Archivos:** `docker-compose.yml`, `sistema_real/`, `simulacion/`, `analisis/` |
| Sin enrutamiento por habilidades. | Se implementan las estrategias Round Robin y Skill-Based Routing.<br>**Archivo:** `simulacion/estrategias.py` |
| Parámetros diferentes entre la API y la simulación. | Ambos componentes usan una fuente única de parámetros.<br>**Archivo:** `config/parametros.py` (`P`) |
| Sin fórmulas ni umbrales explícitos para los KPI. | Se documentan Erlang C y la Ley de Little; los umbrales SLA se implementan y grafican.<br>**Archivos:** `analisis/contraste_mmc.py`, §§4–5 |

## 3. Arquitectura del Prototipo, Telemetría y Parámetros Calibrados

### 3.1 Resumen de Telemetría del Sistema Real Contenerizado

La arquitectura desplegada son **dos contenedores**: `api` (FastAPI/Uvicorn) y `db` (PostgreSQL 16), orquestados con `docker-compose.yml`. Un _middleware_ cronometra **cada petición HTTP** y escribe en `datos/telemetry_log.csv`: `timestamp, método, ruta, status, tiempo_respuesta_ms, pool_en_uso, pool_limite, tickets_abiertos`. En la corrida de carga de referencia (≈170 peticiones sobre los endpoints `/tickets`, `/estado`, `/metricas`) la **latencia media fue ≈ 3.9 ms y el p95 ≈ 6.0 ms**, muy por debajo del SLA técnico de 2.0 s, confirmando que el cuello de botella **no** es la capa HTTP sino la capacidad de atención de los técnicos. El uso del pool se instrumenta desde `engine.pool.checkedout()` para evidenciar el límite duro C6 = 50.

### 3.2 Parámetros y Distribuciones de Entrada del Modelo SimPy

| Parámetro | Modelo y unidad | Fuente |
|---|---|---|
| Llegadas (valle / pico) | Poisson no homogéneo: λ=0.5 / 1.5 tickets/min, por _thinning_ | `config/parametros.py`; Entrega 1, §7 |
| Servicio real | Lognormal: media 15 min, σ_log=0.5 | μ canónico; cola larga realista |
| Servicio markoviano | Exponencial: media 15 min | Contraste M/M/c |
| Factor de especialista (Skill-Based) | 0.80; reduce la media de 15 a 12 min | Garnett & Mandelbaum (2000) |
| Paciencia (C7) | Normal(30, 5) min, truncada en 5 min | Entrega 1, §8 |
| Reintento | Probabilidad 0.40; espera Exp(media 10 min); máximo 2 | `config/parametros.py` |
| Validación y registro (C6) | Constante: 0.8 s | `telemetry_log.csv` |
| Pool de conexiones (C6) | Capacidad: 50 conexiones | `database.py` (`pool_size=50`) |

## 4. Diseño Experimental y Contraste Analítico (M/M/c vs. SimPy)

- **Horizonte operativo:** 480 min (jornada 08:00–16:00). **Warm-up:** 60 min.
- **Horizonte de validación markoviana:** 3000 min + 300 min de warm-up (régimen estacionario, para no sesgar Lq/Wq por truncamiento).
- **Réplicas independientes:** **R = 30** con semillas `42..71` (reproducible).

### 4.1 Tabla de Validación Analítica (Régimen Estacionario Exponencial)

Modelo M/M/9 con λ=0.5, μ=0.0667, a=λ/μ=7.5 Erlangs, ρ=0.8333. Fórmula C de Erlang.

| Métrica | Analítico M/M/c | SimPy: media ± IC 95 % | Diferencia |
|---|---:|---:|---:|
| Utilización (ρ) | 0.833 | 0.825 ± 0.011 | −1.06 % |
| Probabilidad de espera (Pw) | 0.509 | — | — |
| Longitud media de cola (Lq), tickets | 2.546 | 2.517 ± 0.592 | −1.13 % |
| Espera media en cola (Wq), min | 5.091 | 5.032 ± 1.190 | −1.17 % |
| Tiempo medio en sistema (W), min | 20.091 | 20.000 ± 1.303 | −0.45 % |
| Longitud media en sistema (L), tickets | 10.046 | 9.985 ± 0.662 | −0.60 % |

**Ley de Little (verificación):** L = λ·W = 0.5 × 20.091 = 10.046 ≈ L. También Lq = λ·Wq = 0.5 × 5.091 = 2.546 ≈ Lq. La simulación reproduce el modelo analítico con **error < 1.2 %** en todas las métricas, validando el motor.

**Análisis de divergencia al activar la dinámica real:** al pasar del modo markoviano al modo real, las métricas empeoran respecto al M/M/c porque (i) las **llegadas en ráfaga** (λ=1.5 durante dos ventanas) saturan transitoriamente un sistema dimensionado para el valle; (ii) el **servicio Lognormal** tiene cola más larga que la exponencial; y (iii) **abandonos y reintentos** retiran y reinyectan carga. Por eso el M/M/c estacionario _subestima_ la congestión real y es insuficiente como única herramienta de decisión: se requiere la simulación DES. (Dimensionamiento Erlang C completo en `docs/tabla_contraste_mmc.md`.)

## 5. Resultados de la Simulación y Evaluación de Políticas de Decisión

### 5.1 Comparación Cuantitativa de Escenarios

**Resultados por política.** Los valores son media ± IC 95 %. Para p95 y p99 se muestra el promedio del percentil calculado en cada réplica.

| Indicador | Round Robin | Skill-Based |
|---|---:|---:|
| Tiempo total, media (min) | 21.8 ± 0.6 | 17.0 ± 0.6 |
| Tiempo total, p95 (min) | 44.1 ± 1.0 | 37.7 ± 1.3 |
| Tiempo total, p99 (min) | 54.9 ± 2.0 | 46.7 ± 1.4 |
| Espera en cola Wq, media (min) | 7.0 ± 0.5 | 5.0 ± 0.5 |
| Abandono (%) | 13.7 ± 2.0 | 5.4 ± 1.3 |
| Utilización de técnicos (%) | 88.1 ± 1.8 | 77.7 ± 2.1 |

**Cumplimiento de los SLA con c=9 técnicos:**

| Indicador | Objetivo | Round Robin | Skill-Based |
|---|---:|---|---|
| p95 del tiempo total | < 45 min | Cumple (44.1 min) | Cumple (37.7 min) |
| Abandono | < 3 % | No cumple (13.7 %) | No cumple (5.4 %) |
| Utilización | 70–85 % | No cumple (88.1 %) | Cumple (77.7 %) |

Tickets procesados (30 réplicas): Round Robin resolvió 6 563 y abandonaron 1 134 (447 reintentos); Skill-Based resolvió 7 242 y abandonaron 437 (176 reintentos). Figura: `docs/figuras/politicas_kpis.png`.

### 5.2 Análisis de las Preguntas de Decisión

- **P1 — ¿Qué política mantiene p95 < 45 min y abandono < 3 % en alta demanda?** Skill-Based Routing cumple holgadamente el p95 (37.7 < 45) y **reduce el abandono un 61 %** (13.7 % → 5.4 %), pero **ninguna política alcanza por sí sola el 3 %** de abandono con c=9 bajo las ráfagas pico. Round Robin, además, **excede la banda de utilización** (88.1 %). La política recomendada es **Skill-Based**, complementada con refuerzo de personal en pico (ver §6). Evidencia: `docs/figuras/politicas_kpis.png`.
- **P2 — ¿Número mínimo de técnicos (util ≤ 85 %)?** El análisis Erlang C fija **c = 9 para la demanda promedio** (ρ=0.833) y **c = 27 para un pico sostenido** de 1.5 tickets/min. La simulación confirma que c=9 absorbe el valle pero no ráfagas prolongadas: el cuello de botella es la capacidad de atención, no el pool C6 (0 rechazos observados). Evidencia: `docs/figuras/perfil_llegadas.png` y `docs/tabla_contraste_mmc.md`.

## 6. Recomendación de Ingeniería y Declaración de Uso de IA

### 6.1 Recomendación Técnica Final

Desplegar **Skill-Based Routing** como política de producción: con el mismo personal (c=9) mejora los tres KPIs frente a Round Robin y lleva la utilización a la banda objetivo. Como el abandono en pico (5.4 %) aún supera el SLA del 3 %, se recomienda un esquema de **staffing dinámico**: añadir **1–2 técnicos durante las dos ventanas pico** (≈10:30 y ≈14:00), coherente con que Erlang C baja ρ a 0.75 con c=10. El límite C6 (pool=50) no es el cuello de botella actual, pero debe vigilarse con la telemetría si crece la tasa de llegada. La decisión equilibra **costo-beneficio**: evita el sobredimensionamiento a 27 técnicos (pico teórico) usando una mejor política más un refuerzo puntual.

### 6.2 Declaración de Uso de Inteligencia Artificial

| Aspecto | Declaración |
|---|---|
| Herramienta | Asistente de IA (modelo de lenguaje) |
| Uso | Estructuración del repositorio, redacción de documentación y refactorización de clases SimPy/API |
| Verificación del equipo | Se revisaron manualmente las ecuaciones M/M/c y la coherencia de parámetros entre código y documento. También se ejecutó el contraste numérico (error < 1.2 %) y se validaron los KPI con 30 réplicas semilladas. |

La responsabilidad sobre el modelo, los supuestos, los cálculos y las decisiones de diseño corresponde al equipo.

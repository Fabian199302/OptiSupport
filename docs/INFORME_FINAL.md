# archivo: docs/INFORME_FINAL.md

# Informe Final — OptiSupport (Asignación de tareas de soporte técnico)

- **Curso:** Modelos y Simulación (2026-2) — I.U. Pascual Bravo
- **Grupo:** Grupo 3
- **Repositorio:** https://github.com/Fabian199302/OptiSupport
- **Comando de despliegue API:** `docker compose up --build -d`
- **Comando de ejecución SimPy:** `python simulacion/main.py`
- **Comando de contraste M/M/c:** `python analisis/contraste_mmc.py`
- **Comando de sensibilidad:** `python analisis/sensibilidad.py`

| Integrante | Correo institucional | Rol y módulos principales |
|---|---|---|
| Yulisa Stefanny Higuita Rodríguez | yulisa.higuita602@pascualbravo.edu.co | Modelado DES / SimPy y sensibilidad<br>`simulacion/`, `analisis/sensibilidad.py` |
| Fabián Eliécer Montoya | f.montoya@pascualbravo.edu.co | Infraestructura / API / Telemetría<br>`sistema_real/`, `docker-compose.yml`, `datos/` |
| Mateo Corrales Vinasco | mateo.corrales571@pascualbravo.edu.co | Análisis estadístico / Contraste M/M/c e informe<br>`analisis/contraste_mmc.py`, `docs/` |

---

## 1. Resumen Ejecutivo

OptiSupport es un gemelo digital de una mesa de soporte técnico donde llegan tickets no estacionarios que se validan, clasifican y asignan a técnicos finitos bajo reglas de prioridad, paciencia (abandono) y SLA. El problema de ingeniería es decidir **qué política de asignación y qué dimensionamiento** de técnicos minimizan el tiempo de atención y el abandono sin sobredimensionar el personal. Se compararon **Round Robin** (técnicos generalistas) y **Skill-Based Routing** (especialistas con balanceo de carga) sobre 30 réplicas de una jornada de 8 h. Con el supuesto aún no calibrado de que el especialista atiende 20 % más rápido, Skill-Based reduce el abandono de 13.7 % a 5.4 % y el p95 de 44.1 a 37.7 min. Round Robin también cumple el SLA de p95 (44.1 < 45 min). Sin esa ganancia de velocidad, las políticas arrojan resultados cercanos, por lo que la ventaja de Skill-Based depende de validar el factor de servicio con datos reales. Para el abandono, 10 técnicos Skill-Based dejan el resultado en el umbral (3.1 % ± 0.9); 11 lo reducen a 1.6 % ± 0.7, aunque con utilización inferior a la banda objetivo.

## 2. Contexto del Sistema y Subsanación de la Entrega 1

### 2.1 Dinámica del Sistema (Qué fluye, qué espera, qué se satura)

- **Entidades que fluyen:** _tickets_ de soporte con atributos `tipo` (REDES / BD / INFRA), `prioridad` (1 = crítico, 2 = alto, 3 = normal), marca de llegada y tiempo de paciencia individual. La mezcla de llegada es 40/30/30 por tipo y 15/35/50 por prioridad.
- **Recursos y colas de contención:** **9 técnicos** (recurso finito, `simpy`) atienden una cola única ordenada por _prioridad y luego FIFO_. En Round Robin los técnicos son generalistas; en Skill-Based están especializados y se enruta al compatible de **menor carga**. La disciplina es no apropiativa.
- **Límite físico duro (C6) y comportamiento de agentes (C7):** el **pool de 50 conexiones** de la API (`pool_size=50, max_overflow=0`) es el tope físico modelado tanto en el código real (`sistema_real/database.py`) como en la simulación (`simpy.Resource(capacity=50)`). Con la demanda estudiada, el pool configurado en 50 no se satura y no genera rechazos; el cuello de botella son los técnicos. El usuario abandona si su espera supera su paciencia `~ Normal(30, 5)` truncada en 5 min (C7), y reintenta con probabilidad 0.40 hasta 2 veces.

### 2.2 Tabla de Subsanación de la Entrega Parcial 1

| Problema detectado | Corrección y ubicación |
|---|---|
| Tasas inconsistentes: servicio de 15 min/ticket frente a 0.2 tickets/min, con ρ=1.875. | Se establece μ = 1/15 = 0.0667 tickets/min como tasa única, derivada de `tiempo_servicio_min`.<br>**Archivo:** `config/parametros.py` |
| Sistema inestable con c=4 técnicos (ρ=1.875). | Se calibra el sistema con c=9, para obtener ρ=0.833.<br>**Archivo:** `config/parametros.py` (`c_tecnicos`, `rho_base`) |
| Repositorio inicialmente vacío. | Se implementan API FastAPI, PostgreSQL, telemetría, simulación SimPy y contraste M/M/c.<br>**Archivos:** `docker-compose.yml`, `sistema_real/`, `simulacion/`, `analisis/` |
| Sin enrutamiento por habilidades. | Se implementan las estrategias Round Robin y Skill-Based Routing.<br>**Archivo:** `simulacion/estrategias.py` |
| Parámetros diferentes entre la API y la simulación. | Ambos componentes usan una fuente única de parámetros.<br>**Archivo:** `config/parametros.py` (`P`) |
| Sin fórmulas ni umbrales explícitos para los KPI. | Se documentan Erlang C y la Ley de Little; los umbrales SLA se implementan y grafican.<br>**Archivos:** `analisis/contraste_mmc.py`, §§4–5 |
| Cambio de motor de base de datos de SQL Server a PostgreSQL. | Se adopta PostgreSQL 16, integrado como servicio contenerizado y reproducible con Docker Compose.<br>**Archivo:** `docker-compose.yml` |

## 3. Arquitectura del Prototipo, Telemetría y Parámetros Calibrados

### 3.1 Resumen de Telemetría del Sistema Real Contenerizado

La arquitectura desplegada son **dos contenedores**: `api` (FastAPI/Uvicorn) y `db` (PostgreSQL 16), orquestados con `docker-compose.yml`. Un _middleware_ cronometra cada petición HTTP y escribe en `datos/telemetry_log.csv`. En la corrida de verificación se enviaron **300 tickets** y se registraron **331 solicitudes**: 300 `POST /tickets`, 30 `GET /estado` y una solicitud de comprobación de salud. No hubo errores; la latencia media fue **10.549 ms** y el p95 **22.424 ms**, por debajo del SLA técnico de 2.0 s. El uso del pool se instrumenta desde `engine.pool.checkedout()` para observar el límite C6 = 50. Estas mediciones corresponden a esta corrida local y pueden variar con el entorno.

### 3.2 Parámetros y Distribuciones de Entrada del Modelo SimPy

| Parámetro | Modelo y unidad | Fuente |
|---|---|---|
| Llegadas (valle / pico) | Poisson no homogéneo: λ=0.5 / 1.5 tickets/min, por _thinning_ | `config/parametros.py`; Entrega 1, §7 |
| Servicio real | Lognormal: media 15 min, σ_log=0.5 | μ canónico; cola larga realista |
| Servicio markoviano | Exponencial: media 15 min | Contraste M/M/c |
| Factor de especialista (Skill-Based) | 0.80; reduce la media de 15 a 12 min | Supuesto del equipo, aún sin calibrar |
| Paciencia (C7) | Normal(30, 5) min, truncada en 5 min | Entrega 1, §8 |
| Reintento | Probabilidad 0.40; espera Exp(media 10 min); máximo 2 | `config/parametros.py` |
| Validación y registro (C6) | Constante: 0.8 s | `telemetry_log.csv` |
| Pool de conexiones (C6) | Capacidad: 50 conexiones | `database.py` (`pool_size=50`) |

## 4. Diseño Experimental y Contraste Analítico (M/M/c vs. SimPy)

- **Horizonte operativo:** 480 min (jornada 08:00–16:00). **Warm-up:** 60 min.
- **Horizonte de validación markoviana:** 3000 min + 300 min de warm-up (régimen estacionario, para no sesgar Lq/Wq por truncamiento).
- **Réplicas independientes:** **R = 30** con semillas `42..71` (reproducible).
- **Análisis de sensibilidad:** 30 réplicas por escenario; se varía un parámetro a la vez (factor de especialista, técnicos y capacidad del pool C6).

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

**Resultados por política con c=9.** Los valores son media ± IC 95 %. Para p95 y p99 se muestra el promedio del percentil calculado en cada réplica.

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

En las 30 réplicas, Round Robin resolvió 6 563 tickets y registró 1 134 abandonos y 447 reintentos; Skill-Based resolvió 7 242 tickets y registró 437 abandonos y 176 reintentos. Figura: `docs/figuras/politicas_kpis.png`.

### 5.2 Análisis de las Preguntas de Decisión

- **P1 — ¿Qué política mantiene p95 < 45 min y abandono < 3 % en alta demanda?** Con c=9, ambas políticas cumplen el SLA de p95 (44.1 min Round Robin y 37.7 min Skill-Based), pero ninguna alcanza el SLA de abandono < 3 %. Skill-Based reduce el abandono de 13.7 % a 5.4 % con el supuesto de servicio 20 % más rápido. La sensibilidad indica que, si el factor es 1.00, el abandono de Skill-Based (13.3 % ± 2.0) es cercano al de Round Robin (13.7 % ± 2.0); por tanto, se debe validar la ganancia con datos operativos antes de atribuir la mejora a la política de enrutamiento.
- **P2 — ¿Cuántos técnicos se requieren?** Erlang C estima c=9 para la demanda promedio (ρ=0.833) y c=27 para un pico sostenido (λ=1.5). En la sensibilidad con Skill-Based, c=10 produce abandono de 3.1 % ± 0.9 y utilización de 71.1 % ± 1.9; c=11 baja el abandono a 1.6 % ± 0.7, pero también la utilización a 64.9 % ± 2.0, por debajo de la banda objetivo. Estos escenarios mantienen el número de técnicos durante toda la jornada: **no simulan un aumento de personal exclusivo para las ventanas pico**. El pool C6 no es el cuello de botella con capacidad 50. Evidencia: `docs/tabla_contraste_mmc.md` y §5.3.

### 5.3 Análisis de Sensibilidad

Se ejecutaron 30 réplicas por escenario, con las mismas semillas 42–71 y variando un parámetro a la vez. Las celdas muestran media ± IC 95 %; p95 y p99 son percentiles por réplica y luego promediados. El script reproducible es `analisis/sensibilidad.py`.

**a) Factor de servicio del especialista (c=9).** Round Robin no utiliza este factor.

| Escenario | Abandono (%) | p95 (min) | p99 (min) | Utilización (%) | Rechazos C6 |
|---|---:|---:|---:|---:|---:|
| Round Robin | 13.7 ± 2.0 | 44.1 ± 1.0 | 54.9 ± 2.0 | 88.1 ± 1.8 | 0 |
| Skill-Based, factor 0.80 | 5.4 ± 1.3 | 37.7 ± 1.3 | 46.7 ± 1.4 | 77.7 ± 2.1 | 0 |
| Skill-Based, factor 0.90 | 9.2 ± 1.6 | 40.8 ± 1.0 | 51.0 ± 1.5 | 84.8 ± 2.0 | 0 |
| Skill-Based, factor 1.00 | 13.3 ± 2.0 | 44.5 ± 1.2 | 55.3 ± 1.6 | 89.4 ± 1.8 | 0 |

Con factor 1.00, los resultados de abandono son cercanos entre las políticas. La ventaja observada depende del supuesto de que los especialistas atienden más rápido; el factor 0.80 debe calibrarse con datos reales antes de producción.

**b) Número de técnicos (Skill-Based con factor 0.80).** Los resultados de ambas políticas se incluyen para comparar el efecto del dimensionamiento.

| Técnicos / política | Abandono (%) | p95 (min) | p99 (min) | Utilización (%) | Rechazos C6 |
|---|---:|---:|---:|---:|---:|
| c=9, Round Robin | 13.7 ± 2.0 | 44.1 ± 1.0 | 54.9 ± 2.0 | 88.1 ± 1.8 | 0 |
| c=9, Skill-Based | 5.4 ± 1.3 | 37.7 ± 1.3 | 46.7 ± 1.4 | 77.7 ± 2.1 | 0 |
| c=10, Round Robin | 9.5 ± 1.8 | 43.7 ± 1.1 | 54.2 ± 1.7 | 84.1 ± 2.2 | 0 |
| c=10, Skill-Based | 3.1 ± 0.9 | 35.1 ± 1.7 | 44.3 ± 2.0 | 71.1 ± 1.9 | 0 |
| c=11, Round Robin | 5.1 ± 1.1 | 42.1 ± 1.0 | 53.3 ± 1.5 | 79.0 ± 1.6 | 0 |
| c=11, Skill-Based | 1.6 ± 0.7 | 31.9 ± 1.6 | 41.0 ± 1.8 | 64.9 ± 2.0 | 0 |
| c=12, Round Robin | 4.2 ± 1.0 | 40.3 ± 1.6 | 51.0 ± 2.3 | 73.2 ± 1.8 | 0 |
| c=12, Skill-Based | 0.6 ± 0.3 | 29.9 ± 1.5 | 39.3 ± 2.0 | 60.2 ± 1.3 | 0 |

Con c=10, el abandono queda en el umbral del 3 % y la utilización sigue dentro de la banda objetivo. Con c=11, el abandono baja del 3 %, pero la utilización cae por debajo del 70 %. El refuerzo solo durante las dos ventanas pico no se simuló y queda como trabajo futuro.

**c) Capacidad del pool de conexiones C6 (c=9, Skill-Based).**

| Capacidad del pool | Abandono (%) | p95 (min) | p99 (min) | Utilización (%) | Rechazos en 30 réplicas |
|---|---:|---:|---:|---:|---:|
| 50 | 5.4 ± 1.3 | 37.7 ± 1.3 | 46.7 ± 1.4 | 77.7 ± 2.1 | 0 |
| 5 | 5.4 ± 1.3 | 37.7 ± 1.3 | 46.7 ± 1.4 | 77.7 ± 2.1 | 0 |
| 1 | 4.9 ± 1.4 | 36.7 ± 1.1 | 46.5 ± 1.6 | 76.6 ± 1.6 | 86 |

Con pool de 50 y de 5 los resultados coinciden y no hay rechazos; al reducir el pool a 1 se observan 86 rechazos. La validación ocupa la conexión por 0.8 s, así que el límite configurado de 50 queda lejos de activarse en la demanda probada.

## 6. Recomendación de Ingeniería y Declaración de Uso de IA

### 6.1 Recomendación Técnica Final

Skill-Based Routing es la alternativa preferida **si se valida la hipótesis de servicio más rápido del especialista**. Con c=9 cumple el SLA de p95 y la banda de utilización, pero no el SLA de abandono. La sensibilidad recomienda **c=10** como equilibrio: abandono de 3.1 % ± 0.9 (en el umbral) y utilización de 71.1 % ± 1.9. Si el 3 % es un límite estricto, **c=11** reduce el abandono a 1.6 % ± 0.7, aceptando una utilización de 64.9 % ± 2.0, bajo la banda deseada. Estas cifras corresponden a dotación constante durante el horizonte; el refuerzo solo en las ventanas pico es una alternativa de menor costo, pero **no está simulada** y queda como trabajo futuro. El pool C6 de 50 conexiones no es el cuello de botella bajo la demanda probada.

### 6.2 Declaración de Uso de Inteligencia Artificial

| Aspecto | Declaración |
|---|---|
| Herramienta | Asistente de IA (modelo de lenguaje) |
| Uso | Estructuración del repositorio, redacción de documentación y refactorización de clases SimPy/API |
| Verificación del equipo | Se revisaron manualmente las ecuaciones M/M/c y la coherencia de parámetros entre código y documento. También se ejecutó el contraste numérico (error < 1.2 %) y se validaron los KPI con 30 réplicas semilladas. |
| Revisión adicional | Claude (Anthropic) apoyó la revisión del informe y la incorporación del análisis de sensibilidad; el equipo ejecutó y verificó los resultados reportados. |

La responsabilidad sobre el modelo, los supuestos, los cálculos y las decisiones de diseño corresponde al equipo.

# Contraste Analitico M/M/c vs. SimPy (modo markoviano)

Generado automaticamente por `analisis/contraste_mmc.py`.

**Parametros:** lambda = 0.5 tickets/min · mu = 1/15 = 0.06667 tickets/min · c = 9 servidores · a = lambda/mu = 7.500 Erlangs · rho = 0.8333.

**Corrida SimPy de validacion:** horizonte = 3000 min, warm-up = 300 min, 30 replicas (semillas 42..71).

## Tabla de validacion (regimen estacionario exponencial)

| Metrica | M/M/c analitico | SimPy (media ± IC95) | Error rel. (%) |
| :--- | :---: | :---: | :---: |
| Utilizacion (rho) | 0.833 | 0.825 ± 0.011 | -1.06% |
| Prob. de espera (Pw) | 0.509 | — (no medido) | — |
| Lq  (tickets en cola) | 2.546 tickets | 2.517 ± 0.592 tickets | -1.13% |
| Wq  (espera en cola) | 5.091 min | 5.032 ± 1.190 min | -1.17% |
| W   (tiempo en sistema) | 20.091 min | 20.000 ± 1.303 min | -0.45% |
| L   (tickets en sistema) | 10.046 tickets | 9.985 ± 0.662 tickets | -0.60% |

> La Ley de Little se verifica analiticamente: L = lambda · W = 0.5 × 20.091 = 10.046 ≈ L = 10.046 tickets.

## Analisis de dimensionamiento (Erlang C por numero de tecnicos)

| c (tecnicos) | rho | Pw | Lq (tickets) | Wq (min) | W (min) | Lectura |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 4 | 1.875 | — | — | — | — | INESTABLE (rho ≥ 1) |
| 5 | 1.500 | — | — | — | — | INESTABLE (rho ≥ 1) |
| 6 | 1.250 | — | — | — | — | INESTABLE (rho ≥ 1) |
| 7 | 1.071 | — | — | — | — | INESTABLE (rho ≥ 1) |
| 8 | 0.938 | 0.807 | 12.109 | 24.218 | 39.218 | Estable, sobre objetivo 85% |
| 9 | 0.833 | 0.509 | 2.546 | 5.091 | 20.091 | Estable, dentro de 70-85% |
| 10 | 0.750 | 0.307 | 0.920 | 1.840 | 16.840 | Estable, dentro de 70-85% |
| 11 | 0.682 | 0.176 | 0.377 | 0.753 | 15.753 | Estable, holgado |
| 12 | 0.625 | 0.096 | 0.160 | 0.319 | 15.319 | Estable, holgado |
